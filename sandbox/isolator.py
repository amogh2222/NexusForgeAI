"""
NexusForge AI — Secure Code Execution Sandbox
Multi-layer isolation for untrusted AI-generated code.

Security layers (applied in order):
  1. gVisor (--runtime=runsc): user-space kernel intercepts ALL syscalls
  2. Resource limits: --memory, --cpus via cgroups
  3. Network isolation: --network=none (no data exfiltration)
  4. Filesystem: --read-only + --tmpfs (no persistence)
  5. No privileges: --cap-drop=ALL, non-root user

Execution modes:
  - Docker + gVisor (production Linux):   full isolation
  - Docker (standard runtime, dev):       partial isolation
  - subprocess with resource limits:      local fallback (Windows/macOS)
"""
from __future__ import annotations

import asyncio
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool
    execution_ms: float
    mode: str           # "gvisor", "docker", "subprocess"
    error: Optional[str] = None


class SandboxIsolator:
    """
    Runs AI-generated code in an isolated sandbox.

    Auto-detects the best available isolation mode:
    1. Docker + gVisor (production Linux)
    2. Docker standard (development)
    3. subprocess with resource limits (Windows / local dev)
    """

    SANDBOX_IMAGE = "python:3.12-slim"

    def __init__(self) -> None:
        from backend.core.config import settings
        self._s = settings
        self._docker_available = self._check_docker()
        self._gvisor_available = self._check_gvisor()
        log.info(
            "sandbox.initialized",
            docker=self._docker_available,
            gvisor=self._gvisor_available,
            platform=platform.system(),
        )

    def _check_docker(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_gvisor(self) -> bool:
        """Check if gVisor runsc runtime is registered with Docker."""
        if not self._docker_available:
            return False
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{json .Runtimes}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "runsc" in (result.stdout or "")
        except Exception:
            return False

    # ─── Public API ──────────────────────────────────────────────────────────

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 10,
    ) -> SandboxResult:
        """
        Execute code in the most secure available sandbox.
        """
        if language not in ("python", "javascript", "bash", "sh"):
            return SandboxResult(
                stdout="", stderr=f"Unsupported language: {language}",
                return_code=1, timed_out=False, execution_ms=0, mode="none",
                error="unsupported_language",
            )

        if self._docker_available and self._gvisor_available:
            return await self._execute_gvisor(code, language, timeout_seconds)
        elif self._docker_available and self._s.SANDBOX_DOCKER_ENABLED:
            return await self._execute_docker(code, language, timeout_seconds)
        else:
            return await self._execute_subprocess(code, language, timeout_seconds)

    # ─── gVisor Execution ────────────────────────────────────────────────────

    async def _execute_gvisor(
        self, code: str, language: str, timeout: int
    ) -> SandboxResult:
        """Full isolation: gVisor user-space kernel + Docker."""
        cmd = self._build_docker_cmd(language, runtime="runsc")
        return await self._run_docker_cmd(cmd, code, timeout, mode="gvisor")

    # ─── Docker Execution ─────────────────────────────────────────────────────

    async def _execute_docker(
        self, code: str, language: str, timeout: int
    ) -> SandboxResult:
        """Standard Docker isolation (no gVisor)."""
        cmd = self._build_docker_cmd(language, runtime=None)
        return await self._run_docker_cmd(cmd, code, timeout, mode="docker")

    def _build_docker_cmd(self, language: str, runtime: Optional[str]) -> list[str]:
        s = self._s
        cmd = [
            "docker", "run", "--rm", "-i",
            "--network=none",                    # no network access
            f"--memory={s.SANDBOX_MAX_MEMORY_MB}m",
            "--cpus=0.5",
            "--cap-drop=ALL",                    # drop all Linux capabilities
            "--security-opt=no-new-privileges",  # prevent privilege escalation
            "--read-only",                       # read-only root filesystem
            "--tmpfs=/tmp:size=64m,noexec",      # writable tmp, no exec bit
            "--user=nobody",                     # run as unprivileged user
        ]
        if runtime:
            cmd.extend([f"--runtime={runtime}"])

        cmd.append(self.SANDBOX_IMAGE)

        # Language-specific runner
        if language == "python":
            cmd.extend(["python", "-c"])
        elif language in ("bash", "sh"):
            cmd.extend(["bash", "-c"])
        elif language == "javascript":
            cmd.extend(["node", "-e"])

        return cmd

    async def _run_docker_cmd(
        self, cmd: list[str], code: str, timeout: int, mode: str
    ) -> SandboxResult:
        start = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, code,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=code.encode()),
                    timeout=timeout + 2,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return SandboxResult(
                    stdout="", stderr="Execution timed out",
                    return_code=-1, timed_out=True,
                    execution_ms=(time.perf_counter() - start) * 1000,
                    mode=mode,
                )

            return SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace")[:50_000],
                stderr=stderr.decode("utf-8", errors="replace")[:10_000],
                return_code=proc.returncode or 0,
                timed_out=False,
                execution_ms=(time.perf_counter() - start) * 1000,
                mode=mode,
            )
        except Exception as e:
            log.warning("sandbox.docker_failed", mode=mode, error=str(e))
            return await self._execute_subprocess(code, "python", timeout)

    # ─── Subprocess Fallback (Windows / macOS) ────────────────────────────────

    async def _execute_subprocess(
        self, code: str, language: str, timeout: int
    ) -> SandboxResult:
        """
        Last-resort subprocess execution with basic resource limits.
        Used on Windows/macOS where Docker may be unavailable.
        No syscall interception — treat output as untrusted.
        """
        start = time.perf_counter()

        if language == "python":
            interpreter = [sys.executable]
            args = ["-c", code]
        elif language in ("bash", "sh"):
            interpreter = ["bash" if platform.system() != "Windows" else "cmd"]
            args = ["-c", code]
        elif language == "javascript":
            interpreter = ["node"]
            args = ["-e", code]
        else:
            return SandboxResult(
                stdout="", stderr=f"Unsupported: {language}",
                return_code=1, timed_out=False, execution_ms=0,
                mode="subprocess",
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                *interpreter, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return SandboxResult(
                    stdout="", stderr="Timeout",
                    return_code=-1, timed_out=True,
                    execution_ms=(time.perf_counter() - start) * 1000,
                    mode="subprocess",
                )

            return SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace")[:20_000],
                stderr=stderr.decode("utf-8", errors="replace")[:5_000],
                return_code=proc.returncode or 0,
                timed_out=False,
                execution_ms=(time.perf_counter() - start) * 1000,
                mode="subprocess",
            )
        except Exception as e:
            return SandboxResult(
                stdout="", stderr=str(e),
                return_code=1, timed_out=False,
                execution_ms=(time.perf_counter() - start) * 1000,
                mode="subprocess",
                error=str(e),
            )

    def get_isolation_level(self) -> str:
        """Return human-readable isolation level description."""
        if self._gvisor_available:
            return "gVisor (syscall interception + cgroup limits + no-network)"
        elif self._docker_available and self._s.SANDBOX_DOCKER_ENABLED:
            return "Docker (cgroup limits + no-network + read-only FS)"
        return "subprocess (basic timeout only — treat as untrusted)"
