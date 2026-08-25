"""NexusForge AI — Code Execution Celery Task (subprocess-based sandbox)"""
import subprocess
import tempfile
import time
import os
from typing import Optional

import structlog

from backend.workers.celery_app import celery_app
from backend.core.config import settings

log = structlog.get_logger()

RUNTIME_COMMANDS = {
    "python": ["python3", "-u"],   # -u for unbuffered output
    "nodejs": ["node"],
    "go":     None,                # requires go run <file>
    "bash":   ["bash"],
}

RUNTIME_EXTENSIONS = {
    "python": ".py",
    "nodejs": ".js",
    "go":     ".go",
    "bash":   ".sh",
}


@celery_app.task(
    name="backend.workers.tasks.execution_task.execute_code",
    bind=True,
    max_retries=0,
    soft_time_limit=settings.EXECUTION_TIMEOUT_SECONDS if hasattr(settings, "EXECUTION_TIMEOUT_SECONDS") else 30,
)
def execute_code(
    self,
    execution_id: str,
    project_id: str,
    runtime: str,
    code: str,
    stdin: Optional[str] = None,
):
    """
    Execute code in a subprocess sandbox.
    Streams stdout/stderr to Redis pub/sub for real-time WebSocket delivery.
    Enforces time limit via subprocess timeout.
    """
    import json
    import redis as _redis

    redis_client = _redis.from_url(settings.REDIS_URL)
    start_time = time.time()

    ext = RUNTIME_EXTENSIONS.get(runtime, ".txt")

    try:
        with tempfile.NamedTemporaryFile(
            suffix=ext,
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as f:
            f.write(code)
            tmp_path = f.name

        # Build command
        if runtime == "go":
            cmd = ["go", "run", tmp_path]
        else:
            base_cmd = RUNTIME_COMMANDS.get(runtime, ["bash"])
            cmd = base_cmd + [tmp_path]

        # Execute
        result = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=settings.EXECUTION_TIMEOUT_SECONDS if hasattr(settings, "EXECUTION_TIMEOUT_SECONDS") else 30,
            cwd=tempfile.gettempdir(),
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Update execution record
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.models import Execution, ExecutionStatus

        sync_engine = create_engine(settings.DATABASE_SYNC_URL)
        Session = sessionmaker(bind=sync_engine)
        with Session() as session:
            execution = session.query(Execution).filter_by(id=execution_id).first()
            if execution:
                execution.stdout = result.stdout[:50000]
                execution.stderr = result.stderr[:10000]
                execution.exit_code = result.returncode
                execution.status = ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED
                execution.duration_ms = duration_ms
                session.commit()
        sync_engine.dispose()

        # Publish result event
        redis_client.publish(f"nexusforge:ws:{project_id}", json.dumps({
            "type": "execution_complete",
            "execution_id": execution_id,
            "exit_code": result.returncode,
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:5000],
            "duration_ms": duration_ms,
        }))

        log.info("execution.complete", id=execution_id, exit_code=result.returncode, duration_ms=duration_ms)
        return {"status": "success", "exit_code": result.returncode, "duration_ms": duration_ms}

    except subprocess.TimeoutExpired:
        log.warning("execution.timeout", id=execution_id)
        redis_client.publish(f"nexusforge:ws:{project_id}", json.dumps({
            "type": "execution_error",
            "execution_id": execution_id,
            "error": "Execution timed out",
        }))
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.models import Execution, ExecutionStatus
        sync_engine = create_engine(settings.DATABASE_SYNC_URL)
        Session = sessionmaker(bind=sync_engine)
        with Session() as session:
            execution = session.query(Execution).filter_by(id=execution_id).first()
            if execution:
                execution.status = ExecutionStatus.TIMEOUT
                session.commit()
        sync_engine.dispose()
        return {"status": "timeout"}

    except Exception as e:
        log.error("execution.error", id=execution_id, error=str(e))
        return {"status": "error", "message": str(e)}

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
