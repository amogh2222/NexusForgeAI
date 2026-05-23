"""NexusForge AI — Metrics stub (Prometheus setup)."""
from fastapi import FastAPI


def setup_metrics(app: FastAPI) -> None:
    """Prometheus metrics are configured via prometheus-fastapi-instrumentator in main.py."""
    pass
