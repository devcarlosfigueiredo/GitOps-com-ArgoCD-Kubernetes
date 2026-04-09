"""
FastAPI application — GitOps Demo
Deployada via ArgoCD com sync automático a partir do Git.
"""

import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="GitOps Demo API",
    description="Aplicação deployada via ArgoCD com GitOps real.",
    version=os.getenv("APP_VERSION", "0.0.1"),
)

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
DEPLOYED_AT = datetime.utcnow().isoformat()


@app.get("/", response_class=JSONResponse)
async def root():
    return {
        "app": "gitops-demo",
        "version": os.getenv("APP_VERSION", "0.0.1"),
        "environment": ENVIRONMENT,
        "message": "Deployed via ArgoCD — Git is the source of truth.",
        "deployed_at": DEPLOYED_AT,
    }


@app.get("/health", response_class=JSONResponse)
async def health():
    """Liveness probe para o Kubernetes."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/ready", response_class=JSONResponse)
async def ready():
    """Readiness probe para o Kubernetes."""
    return {"status": "ready", "environment": ENVIRONMENT}


@app.get("/info", response_class=JSONResponse)
async def info():
    """Informação sobre o deploy actual."""
    return {
        "app": "gitops-demo",
        "version": os.getenv("APP_VERSION", "0.0.1"),
        "environment": ENVIRONMENT,
        "git_commit": os.getenv("GIT_COMMIT", "unknown"),
        "image_tag": os.getenv("IMAGE_TAG", "unknown"),
    }
