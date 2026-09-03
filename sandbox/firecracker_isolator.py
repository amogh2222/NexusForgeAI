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
import uuid

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
        socket_path = f"/tmp/firecracker_{uuid.uuid4().hex[:8]}.socket"

        try:
            # 1. Start Firecracker process
            fc_proc = await asyncio.create_subprocess_exec(
                "firecracker", "--api-sock", socket_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for socket
            for _ in range(50):
                if os.path.exists(socket_path):
                    break
                await asyncio.sleep(0.1)

            # 2. Configure MicroVM via HTTP API over Unix Socket
            import httpx
            transport = httpx.AsyncHTTPTransport(uds=socket_path)
            async with httpx.AsyncClient(transport=transport) as client:
                # Set boot source
                await client.put(
                    "http://localhost/boot-source",
                    json={
                        "kernel_image_path": "/var/lib/firecracker/vmlinux",
                        # Pass the script to execute via kernel boot args for init
                        "boot_args": f"console=ttyS0 reboot=k panic=1 pci=off init=/bin/sh -c '{self._build_execution_script(code, language)} > /dev/ttyS0 2>&1; poweroff -f'"
                    }
                )

                # Set root drive
                await client.put(
                    "http://localhost/drives/rootfs",
                    json={
                        "drive_id": "rootfs",
                        "path_on_host": "/var/lib/firecracker/rootfs.ext4",
                        "is_root_device": True,
                        "is_read_only": True
                    }
                )

                # Start VM
                await client.put(
                    "http://localhost/actions",
                    json={"action_type": "InstanceStart"}
                )

            # 3. Read output from serial console (stdout/stderr of the Firecracker process)
            try:
                stdout, stderr = await asyncio.wait_for(
                    fc_proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                fc_proc.kill()
                return SandboxResult(
                    stdout="", stderr="Firecracker execution timed out",
                    return_code=-1, timed_out=True,
                    execution_ms=(time.perf_counter() - start) * 1000,
                    mode="firecracker",
                )

            # Cleanup socket
            if os.path.exists(socket_path):
                os.remove(socket_path)

            return SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=fc_proc.returncode or 0,
                timed_out=False,
                execution_ms=(time.perf_counter() - start) * 1000,
                mode="firecracker",
            )
        except Exception as e:
            log.warning("firecracker.failed", error=str(e))
            if os.path.exists(socket_path):
                os.remove(socket_path)
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
