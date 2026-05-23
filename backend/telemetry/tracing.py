"""NexusForge AI — Tracing stub (OpenTelemetry setup)."""
from fastapi import FastAPI


def setup_tracing(app: FastAPI) -> None:
    """OpenTelemetry tracing — configure exporters here for production."""
    pass
