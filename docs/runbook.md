# Runbook Operacional — GitOps ArgoCD

> **Regra de ouro:** O Git é a única fonte de verdade. Toda a acção operacional começa no Git — nunca no cluster directamente.

---

## 1. Bootstrap Inicial do Cluster

### Pré-requisitos
```bash
# Ferramentas necessárias
kubectl version --client      # >= 1.28
helm version                  # >= 3.14
argocd version --client       # >= 2.10
kustomize version             # >= 5.4
```

### Instalar ArgoCD via Helm
```bash
# Adicionar repo Helm do ArgoCD
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Instalar ArgoCD com as nossas configurações
kubectl create namespace argocd
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd \
  --values gitops/argocd/argocd-install/values.yaml \
  --wait

# Verificar pods em execução
kubectl get pods -n argocd
```

### Obter password inicial do admin
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo

# Login via CLI
argocd login argocd.gitops-demo.example.com \
  --username admin \
  --password <password-acima>
```

### Criar AppProject e bootstrap via App of Apps
```bash
# Aplicar o AppProject (RBAC)
kubectl apply -f gitops/argocd/appproject.yaml

# Aplicar a Root App (App of Apps pattern)
# Isto cria todas as Applications automaticamente
kubectl apply -f gitops/argocd/root-app.yaml -n argocd

# Verificar
argocd app list
```

---

## 2. Verificar Estado das Applications

```bash
# Listar todas as apps e o seu estado
argocd app list

# Estado detalhado de uma app
argocd app get myapp-dev
argocd app get myapp-prod

# Ver diff entre Git e cluster (antes de sincronizar)
argocd app diff myapp-prod

# Histórico de deployments
argocd app history myapp-prod
```

---

## 3. Sincronização Manual (Prod)

```bash
# Ver diff primeiro (boa prática)
argocd app diff myapp-prod

# Sincronizar prod manualmente
argocd app sync myapp-prod

# Sincronizar com dry-run (não aplica — só simula)
argocd app sync myapp-prod --dry-run

# Forçar sincronização (ignora cache)
argocd app sync myapp-prod --force

# Sincronizar apenas recursos específicos
argocd app sync myapp-prod \
  --resource apps:Deployment:prod-myapp
```

---

## 4. Rollback — Procedimento Completo

### Opção A: Git Revert (recomendado — histórico preservado)

```bash
# 1. Ver histórico do overlay de prod
git log --oneline gitops/apps/myapp/overlays/prod/

# Output exemplo:
# abc1234 chore(gitops): update prod image tag to sha-def5678
# bcd2345 chore(gitops): update prod image tag to sha-abc1234  ← boa versão
# cde3456 chore(gitops): update prod image tag to sha-789abcd

# 2. Reverter o commit problemático (cria novo commit)
git revert abc1234 --no-edit
git push origin main

# 3. ArgoCD detecta automaticamente e sincroniza
# (ou forçar sync manual em prod)
argocd app sync myapp-prod

# 4. Verificar que prod voltou ao estado anterior
argocd app get myapp-prod
kubectl get pods -n myapp-prod
```

### Opção B: ArgoCD Rollback via CLI (usa histórico interno do ArgoCD)

```bash
# Ver histórico com IDs de revisão
argocd app history myapp-prod

# ID  DATE                           REVISION
# 1   2024-01-15 10:00:00 +0000 UTC  abc1234
# 2   2024-01-15 14:30:00 +0000 UTC  bcd2345  ← voltar aqui
# 3   2024-01-15 16:00:00 +0000 UTC  cde3456

# Rollback para a revisão 2
argocd app rollback myapp-prod 2

# ATENÇÃO: Este método não actualiza o Git.
# Após o rollback, o ArgoCD fica em modo "out of sync".
# Fazer sempre o git revert para manter consistência.
```

### Opção C: Rollback de Emergência sem ArgoCD CLI

```bash
# Directamente via kubectl (APENAS em emergência absoluta)
# ArgoCD irá reverter este estado na próxima sincronização
kubectl rollout undo deployment/prod-myapp -n myapp-prod

# Imediatamente após: fazer git revert para alinhar o Git
```

---

## 5. Promoção Dev → Prod

### Via GitHub Actions (recomendado)

```bash
# Aceder a: GitHub → Actions → "Promote dev → prod"
# Preencher:
#   - image_tag: sha-abc1234 (tag testada em dev)
#   - reason: "Feature X testada e aprovada em dev"
# Clicar "Run workflow"
# Revisar e mergir o PR criado automaticamente
```

### Via linha de comando

```bash
# 1. Verificar tag actual em dev
cat gitops/apps/myapp/overlays/dev/kustomization.yaml | grep newTag

# 2. Criar branch de promoção
git checkout -b promote/prod-sha-abc1234

# 3. Actualizar tag em prod
cd gitops/apps/myapp/overlays/prod
kustomize edit set image \
  ghcr.io/YOUR_ORG/gitops-demo=ghcr.io/YOUR_ORG/gitops-demo:sha-abc1234

# 4. Commit e PR
git add kustomization.yaml
git commit -m "chore(gitops): promote sha-abc1234 to prod"
git push origin promote/prod-sha-abc1234
# Abrir PR no GitHub → Mergir após aprovação
```

---

## 6. Debugging de Sync Failures

```bash
# Ver detalhes do erro de sync
argocd app get myapp-prod --show-operation

# Ver eventos do Kubernetes no namespace
kubectl get events -n myapp-prod --sort-by='.lastTimestamp'

# Ver logs do pod que falhou
kubectl logs -n myapp-prod -l app.kubernetes.io/name=myapp --previous

# Ver logs do ArgoCD (repo server)
kubectl logs -n argocd -l app.kubernetes.io/component=repo-server

# Forçar refresh (ArgoCD re-lê o repositório Git)
argocd app get myapp-prod --refresh
```

---

## 7. Self-Healing — Verificar e Testar

```bash
# Simular mudança manual (para testar self-healing)
kubectl scale deployment prod-myapp -n myapp-prod --replicas=10

# Aguardar ~3 minutos e verificar
kubectl get deployment prod-myapp -n myapp-prod
# replicas deve ter voltado a 3 (estado do Git)

# Ver no histórico do ArgoCD que o self-heal foi aplicado
argocd app history myapp-prod
```

---

## 8. Gestão de Secrets

```bash
# Criar secret para o registry (GHCR)
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN \
  --namespace myapp-dev

kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN \
  --namespace myapp-prod

# Secret para notificações Slack (ArgoCD Notifications)
kubectl create secret generic argocd-notifications-secret \
  --from-literal=slack-token=xoxb-YOUR-SLACK-TOKEN \
  --namespace argocd
```

---

## 9. Monitorização e Alertas

```bash
# Verificar métricas do ArgoCD (requer Prometheus)
kubectl port-forward svc/argocd-metrics 8082:8082 -n argocd
# http://localhost:8082/metrics

# Métricas importantes:
# argocd_app_info — estado de todas as apps
# argocd_app_sync_total — total de syncs
# argocd_app_health_status — estado de saúde

# Verificar Grafana dashboard (se configurado)
kubectl port-forward svc/grafana 3000:3000 -n monitoring
```

---

## 10. Checklist de Deploy para Produção

Antes de cada promoção dev → prod:

- [ ] Todos os testes passaram no CI
- [ ] Scan de vulnerabilidades sem CVEs críticos
- [ ] Métricas de dev verificadas (CPU, memória, error rate)
- [ ] `argocd app diff myapp-prod` revisto e aprovado
- [ ] Janela de manutenção confirmada (08:00-18:00 UTC, Seg-Sex)
- [ ] Pelo menos 1 aprovação no PR de promoção
- [ ] Runbook de rollback acessível e testado
- [ ] Canal #deployments no Slack monitorizado durante o deploy

---

## Contactos de Escalada

| Situação | Contacto |
|----------|----------|
| Deploy stuck > 10 min | Platform Team |
| Prod down | On-call → PagerDuty |
| Cluster inacessível | Cloud Provider Support |
