# GitOps com ArgoCD — Deploy Contínuo Real

> **Git é a única fonte de verdade.** Nenhum `kubectl apply` manual em produção. Nenhum script de deploy. O ArgoCD reconcilia o cluster com o estado declarado no Git — automaticamente, continuamente, auditavelmente.

---

## Estrutura do Projecto

```
gitops-argocd-demo/
│
├── app/                              # Aplicação FastAPI
│   └── main.py                       # API com /health, /ready, /info
│
├── tests/                            # Testes unitários (pytest)
│   └── test_main.py
│
├── Dockerfile                        # Multi-stage build (non-root, SBOM-ready)
├── requirements.txt
│
├── gitops/                           # Manifests Kubernetes — fonte de verdade
│   ├── apps/
│   │   └── myapp/
│   │       ├── base/                 # Recursos base (herdados pelos overlays)
│   │       │   ├── deployment.yaml
│   │       │   ├── service.yaml
│   │       │   └── kustomization.yaml
│   │       └── overlays/
│   │           ├── dev/              # Dev: 1 réplica, sync automático
│   │           │   ├── kustomization.yaml  ← CI actualiza image tag aqui
│   │           │   ├── patch-replicas.yaml
│   │           │   └── patch-resources.yaml
│   │           └── prod/             # Prod: 3 réplicas, sync manual
│   │               ├── kustomization.yaml  ← Actualizado via PR
│   │               ├── patch-replicas.yaml
│   │               ├── patch-resources.yaml
│   │               ├── ingress.yaml
│   │               └── poddisruptionbudget.yaml
│   │
│   └── argocd/
│       ├── root-app.yaml             # App of Apps — bootstrap
│       ├── appproject.yaml           # RBAC e permissões
│       ├── application-dev.yaml      # Application dev (referência)
│       ├── application-prod.yaml     # Application prod (referência)
│       ├── applicationset.yaml       # Gera apps dev+prod de um único YAML
│       └── argocd-install/
│           └── values.yaml           # Helm values para instalar ArgoCD
│
├── .github/workflows/
│   ├── ci.yml                        # Build → Push → Update tag
│   └── promote.yml                   # Promoção dev → prod via PR
│
└── docs/
    ├── architecture.md               # Diagramas e explicação da arquitectura
    └── runbook.md                    # Rollback, promoção, troubleshooting
```

---

## Fluxo GitOps

```
Developer → git push → GitHub Actions CI
                            │
                    ┌───────▼────────┐
                    │  1. pytest      │
                    │  2. docker build│
                    │  3. ghcr push   │
                    │  4. kustomize   │
                    │     edit image  │
                    │  5. git push    │
                    └───────┬────────┘
                            │ (actualiza image tag no Git)
                            │
                    ┌───────▼────────┐
                    │    ArgoCD      │
                    │ (pull-based)   │
                    │                │
                    │ Detecta diff   │
                    │ Git ≠ Cluster  │
                    │                │
                    │ Reconcilia →   │
                    │ kubectl apply  │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │   Kubernetes   │
                    │   Cluster      │
                    │                │
                    │ Estado ==      │
                    │ Estado Git ✓   │
                    └────────────────┘
```

---

## Início Rápido

### 1. Instalar ArgoCD

```bash
helm repo add argo https://argoproj.github.io/argo-helm && helm repo update

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --values gitops/argocd/argocd-install/values.yaml --wait

# Obter password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

### 2. Bootstrap — App of Apps

```bash
# Uma única aplicação do argocd para gerir todas as outras
kubectl apply -f gitops/argocd/appproject.yaml
kubectl apply -f gitops/argocd/root-app.yaml -n argocd

# Verificar
argocd app list
```

### 3. Configurar GitHub Actions

```bash
# Secrets necessários no repositório GitHub:
# Settings → Secrets → Actions

GIT_AUTOMATION_TOKEN   # PAT com permissão contents:write e pull-requests:write
```

### 4. Primeiro Deploy

```bash
# Push para develop → CI faz build + push + actualiza tag
git push origin develop

# ArgoCD sincroniza automaticamente em ~3 minutos
argocd app get myapp-dev
```

---

## Comandos Essenciais

```bash
# Estado de todas as apps
argocd app list

# Ver diff antes de sincronizar
argocd app diff myapp-prod

# Sincronizar prod manualmente
argocd app sync myapp-prod

# Rollback (via Git — recomendado)
git revert <commit-sha> && git push origin main

# Rollback via ArgoCD
argocd app history myapp-prod
argocd app rollback myapp-prod <id>

# Forçar refresh (re-lê Git)
argocd app get myapp-prod --refresh
```

---

## Funcionalidades Implementadas

| Funcionalidade | Estado | Detalhes |
|----------------|--------|---------|
| ArgoCD via Helm | ✅ | `gitops/argocd/argocd-install/values.yaml` |
| ApplicationSet multi-ambiente | ✅ | `gitops/argocd/applicationset.yaml` |
| CI: build + push + update tag | ✅ | `.github/workflows/ci.yml` |
| Sync automático (dev) | ✅ | `automated.selfHeal: true` |
| Self-healing | ✅ | Reverte kubectl manuais |
| Rollback via Git revert | ✅ | Ver runbook.md |
| RBAC por AppProject | ✅ | `gitops/argocd/appproject.yaml` |
| Notificações Slack | ✅ | Helm values: notifications |
| Scan de vulnerabilidades (Trivy) | ✅ | CI: bloqueia CVEs críticos |
| SBOM gerado no CI | ✅ | anchore/sbom-action |
| PodDisruptionBudget (prod) | ✅ | Mínimo 2 réplicas disponíveis |
| HPA (autoscaling) | ✅ | CPU/Memory based |
| Promoção dev→prod via PR | ✅ | `.github/workflows/promote.yml` |
| Sync Windows (prod) | ✅ | Apenas horário de negócio |

---

## Documentação

- [Arquitectura detalhada](docs/architecture.md) — diagramas, componentes, fluxos
- [Runbook operacional](docs/runbook.md) — rollback, promoção, troubleshooting, bootstrap

---

## Tecnologias

`Python` · `FastAPI` · `Docker` · `Kubernetes` · `ArgoCD` · `Kustomize` · `GitHub Actions` · `Helm` · `Trivy` · `Prometheus`

---

## Demonstra

- **GitOps maduro**: declarativo, auditável, reversível via Git
- **Separação CI/CD**: CI faz build, CD (ArgoCD) faz deploy
- **Multi-ambiente**: dev automático, prod com aprovação humana
- **Segurança**: non-root, SBOM, scan de vulnerabilidades, RBAC
- **Operações**: self-healing, rollback, sync windows, notificações

> Diferenciador forte para vagas de **Platform Engineer** e **SRE** em empresas com múltiplos ambientes Kubernetes.
