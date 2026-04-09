# Arquitectura GitOps com ArgoCD

## Visão Geral

Este projecto implementa **GitOps real**: o repositório Git é a **única e absoluta fonte de verdade** para o estado da infraestrutura. Nenhum humano faz `kubectl apply` directamente em produção.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUXO GITOPS COMPLETO                        │
└─────────────────────────────────────────────────────────────────────┘

  Developer                Git Repository          Kubernetes Cluster
  ─────────               ────────────────         ──────────────────
      │                         │                         │
      │  git push (código)      │                         │
      │────────────────────────►│                         │
      │                         │                         │
      │            GitHub Actions CI                      │
      │                    ┌────┴────┐                    │
      │                    │ 1. Test │                    │
      │                    │ 2. Build│                    │
      │                    │ 3. Push │                    │
      │                    │ 4. Tag  │                    │
      │                    └────┬────┘                    │
      │                         │                         │
      │  git push (image tag)   │                         │
      │                         │                         │
      │                    ┌────┴────────────┐           │
      │                    │   ArgoCD        │           │
      │                    │  (Pull-based)   │           │
      │                    │                 │           │
      │                    │ Detecta alteração│          │
      │                    │ no Git a cada   │           │
      │                    │ 3 minutos       │           │
      │                    └────────┬────────┘           │
      │                             │                     │
      │                             │  kubectl apply      │
      │                             │ (via API server)    │
      │                             │────────────────────►│
      │                             │                     │
      │                             │◄────────────────────│
      │                             │   Estado actual     │
      │                             │                     │
      │                    Loop de reconciliação          │
      │                    Git state == Cluster state?    │
      │                    Se não → reconcilia            │
      │                    Se sim → nada a fazer          │
```

## Componentes

### 1. FastAPI Application
- API REST simples em Python
- Endpoints: `/`, `/health`, `/ready`, `/info`
- Probes de liveness e readiness para o Kubernetes
- Containerizada com Docker multi-stage build

### 2. Kustomize — Overlays por Ambiente

```
gitops/apps/myapp/
├── base/                  ← Recursos comuns (base)
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
└── overlays/
    ├── dev/               ← Customizações de dev
    │   ├── kustomization.yaml  ← CI actualiza o image tag aqui
    │   ├── patch-replicas.yaml (1 réplica)
    │   └── patch-resources.yaml (recursos reduzidos)
    └── prod/              ← Customizações de prod
        ├── kustomization.yaml  ← Tag promovida via PR
        ├── patch-replicas.yaml (3 réplicas + anti-affinity)
        ├── patch-resources.yaml (recursos generosos)
        ├── ingress.yaml
        └── poddisruptionbudget.yaml
```

### 3. ArgoCD — Motor GitOps

| Componente | Função |
|-----------|--------|
| **Application** | Mapeia Git path → Kubernetes namespace |
| **ApplicationSet** | Gera Applications para múltiplos ambientes |
| **AppProject** | RBAC: quem pode fazer o quê em cada ambiente |
| **Image Updater** | Monitoriza registry e actualiza tags no Git |
| **Notifications** | Alertas Slack em sync/falha |

### 4. GitHub Actions CI

O CI tem **apenas 3 responsabilidades**:
1. Executar testes
2. Build e push da imagem Docker
3. Actualizar o image tag no repositório Git

**O CI nunca faz deploy.** O deploy é responsabilidade do ArgoCD.

## Fluxo de Deploy por Ambiente

### Dev (automático)
```
git push → develop
    → CI: build + push + update tag em overlays/dev/
    → ArgoCD detecta alteração em develop
    → Sync automático para myapp-dev namespace
    → ✅ Deploy em ~3 minutos
```

### Prod (via PR)
```
Workflow "Promote" → cria PR com novo tag em overlays/prod/
    → Revisão e aprovação do PR
    → Merge em main
    → ArgoCD detecta alteração em main
    → Sync manual (operador confirma na UI)
    → ✅ Deploy em prod com auditoria completa
```

## Self-Healing

Se alguém fizer `kubectl apply` manual ou editar recursos directamente:

```
Operador faz: kubectl scale deployment prod-myapp --replicas=10

ArgoCD detecta drift em ~3 minutos:
    Estado Git: replicas=3
    Estado cluster: replicas=10
    → ArgoCD reverte para replicas=3 automaticamente
    → Notificação Slack: "Self-heal applied"
```

## Segurança

| Camada | Mecanismo |
|--------|-----------|
| **Imagem** | Non-root user, readOnlyRootFilesystem, capabilities drop |
| **ArgoCD** | SSO via Dex, RBAC por role, AppProject |
| **CI** | SBOM gerado, scan Trivy (bloqueia CVEs críticos) |
| **Cluster** | PodDisruptionBudget, ResourceQuota por namespace |
| **Git** | Branch protection, PR obrigatório para main |

## Rollback

O rollback em GitOps é sempre via Git — nunca via `kubectl`:

```bash
# 1. Identificar o commit a reverter
git log --oneline gitops/apps/myapp/overlays/prod/

# 2. Reverter (cria novo commit — histórico preservado)
git revert <commit-sha>
git push origin main

# 3. ArgoCD detecta e sincroniza automaticamente
# Prod volta ao estado anterior em ~3 minutos
```

Ver [runbook.md](runbook.md) para instruções detalhadas.
