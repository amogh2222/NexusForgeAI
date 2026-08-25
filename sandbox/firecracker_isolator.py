"""
NexusForge AI — Firecracker MicroVM Sandbox
Provides strong isolation for agent-generated code using Firecracker.
Falls back to standard Docker sandbox if Firecracker/firectl is unavailable.
"""
from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import time
from typing import Optional

import structlog

from sandbox.isolator import SandboxIsolator, SandboxResult

log = structlog.get_logger()

class FirecrackerIsolator(SandboxIsolator):
    """
    Runs code inside a Firecracker microVM for maximum isolation.
    """
    
    def __init__(self) -> None:
        super().__init__()
        self._firecracker_available = self._check_firecracker()
        log.info("firecracker.initialized", available=self._firecracker_available)

    def _check_firecracker(self) -> bool:
        if platform.system() != "Linux":
            return False
        try:
            result = subprocess.run(["firectl", "--version"], capture_output=True, timeout=2)
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, code: str, language: str = "python", timeout_seconds: int = 10) -> SandboxResult:
        if not self._firecracker_available:
            log.warning("firecracker.unavailable", fallback="docker_or_subprocess")
            return await super().execute(code, language, timeout_seconds)

        return await self._execute_firecracker(code, language, timeout_seconds)

    async def _execute_firecracker(self, code: str, language: str, timeout: int) -> SandboxResult:
        start = time.perf_counter()
        
        # This is a conceptual implementation of wrapping the execution in a Firecracker microVM
        # In a real setup, we would inject the code into a rootfs, start the VM, execute, and read results via virtio
        cmd = [
            "firectl",
            "--kernel=/var/lib/firecracker/vmlinux",
            "--root-drive=/var/lib/firecracker/rootfs.ext4",
            "--cpu-template=T2",
            f"--execute={self._build_execution_script(code, language)}"
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout + 5,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return SandboxResult(
                    stdout="", stderr="Firecracker execution timed out",
                    return_code=-1, timed_out=True,
                    execution_ms=(time.perf_counter() - start) * 1000,
                    mode="firecracker",
                )

            return SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=proc.returncode or 0,
                timed_out=False,
                execution_ms=(time.perf_counter() - start) * 1000,
                mode="firecracker",
            )
        except Exception as e:
            log.warning("firecracker.failed", error=str(e))
            return await super().execute(code, language, timeout)

    def _build_execution_script(self, code: str, language: str) -> str:
        # Escaping code for inline execution
        escaped = code.replace("'", "'\\''")
        if language == "python":
            return f"python3 -c '{escaped}'"
        elif language == "javascript":
            return f"node -e '{escaped}'"
        else:
            return f"bash -c '{escaped}'"

    def get_isolation_level(self) -> str:
        if self._firecracker_available:
            return "Firecracker microVM (Hardware Virtualization)"
        return super().get_isolation_level()
