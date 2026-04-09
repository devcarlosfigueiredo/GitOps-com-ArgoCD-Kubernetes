# =============================================================================
# Dockerfile — GitOps Demo API
# Multi-stage build: imagem final mínima e segura para produção.
# A tag da imagem é gerida pelo CI e actualizada no Git pelo GitHub Actions.
# ArgoCD detecta a alteração no Git e sincroniza automaticamente.
# =============================================================================

# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Instalar dependências de sistema necessárias para compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Metadados da imagem (OCI Image Spec)
LABEL org.opencontainers.image.title="gitops-demo"
LABEL org.opencontainers.image.description="FastAPI app deployada via ArgoCD GitOps"
LABEL org.opencontainers.image.source="https://github.com/YOUR_ORG/gitops-argocd-demo"

# Utilizador não-root por segurança
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copiar dependências compiladas do builder
COPY --from=builder /install /usr/local

# Copiar código da aplicação
COPY app/ .

# Variáveis de ambiente com defaults seguros
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    APP_VERSION=unknown \
    GIT_COMMIT=unknown \
    IMAGE_TAG=unknown

# Mudar para utilizador não-root
USER appuser

EXPOSE 8000

# Healthcheck nativo do Docker (complementa as probes do Kubernetes)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Servidor de produção: uvicorn com múltiplos workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
