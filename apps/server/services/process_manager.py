"""
Agent Process Manager
=====================

Manages the lifecycle of agent subprocesses per project.
Provides start/stop/pause/resume functionality with cross-platform support.
"""

import asyncio
import logging
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Literal, Set

import psutil

logger = logging.getLogger(__name__)

# Patterns for sensitive data that should be redacted from output
SENSITIVE_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',  # Anthropic API keys
    r'ANTHROPIC_API_KEY=[^\s]+',
    r'api[_-]?key[=:][^\s]+',
    r'token[=:][^\s]+',
    r'password[=:][^\s]+',
    r'secret[=:][^\s]+',
    r'ghp_[a-zA-Z0-9]{36,}',  # GitHub personal access tokens
    r'gho_[a-zA-Z0-9]{36,}',  # GitHub OAuth tokens
    r'ghs_[a-zA-Z0-9]{36,}',  # GitHub server tokens
    r'ghr_[a-zA-Z0-9]{36,}',  # GitHub refresh tokens
    r'aws[_-]?access[_-]?key[=:][^\s]+',  # AWS keys
    r'aws[_-]?secret[=:][^\s]+',
]


def sanitize_output(line: str) -> str:
    """Remove sensitive information from output lines."""
    for pattern in SENSITIVE_PATTERNS:
        line = re.sub(pattern, '[REDACTED]', line, flags=re.IGNORECASE)
    return line


class AgentProcessManager:
    """
    Manages agent subprocess lifecycle for a single project.

    Provides start/stop/pause/resume with cross-platform support via psutil.
    Supports multiple output callbacks for WebSocket clients.
    """

    def __init__(
        self,
        project_name: str,
        project_dir: Path,
        root_dir: Path,
    ):
        """
        Initialize the process manager.

        Args:
            project_name: Name of the project
            project_dir: Absolute path to the project directory
            root_dir: Root directory of the autonomous-coding-ui project
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.root_dir = root_dir
        self.process: subprocess.Popen | None = None
        self._status: Literal["stopped", "running", "paused", "crashed"] = "stopped"
        self.started_at: datetime | None = None
        self._output_task: asyncio.Task | None = None
        self.yolo_mode: bool = False  # YOLO mode for rapid prototyping
        self.mode: str | None = None  # Optional run mode (e.g., regression)
        self.model: str | None = None  # Optional model override

        # Support multiple callbacks (for multiple WebSocket clients)
        self._output_callbacks: Set[Callable[[str], Awaitable[None]]] = set()
        self._status_callbacks: Set[Callable[[str], Awaitable[None]]] = set()
        self._callbacks_lock = threading.Lock()

        # Lock file to prevent multiple instances (stored in project directory)
        self.lock_file = self.project_dir / ".agent.lock"

    @property
    def status(self) -> Literal["stopped", "running", "paused", "crashed"]:
        return self._status

    @status.setter
    def status(self, value: Literal["stopped", "running", "paused", "crashed"]):
        old_status = self._status
        self._status = value
        if old_status != value:
            self._notify_status_change(value)

    def _notify_status_change(self, status: str) -> None:
        """Notify all registered callbacks of status change."""
        with self._callbacks_lock:
            callbacks = list(self._status_callbacks)

        for callback in callbacks:
            try:
                # Schedule the callback in the event loop
                loop = asyncio.get_running_loop()
                loop.create_task(self._safe_callback(callback, status))
            except RuntimeError:
                # No running event loop
                pass

    async def _safe_callback(self, callback: Callable, *args) -> None:
        """Safely execute a callback, catching and logging any errors."""
        try:
            await callback(*args)
        except Exception as e:
            logger.warning(f"Callback error: {e}")

    def add_output_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Add a callback for output lines."""
        with self._callbacks_lock:
            self._output_callbacks.add(callback)

    def remove_output_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Remove an output callback."""
        with self._callbacks_lock:
            self._output_callbacks.discard(callback)

    def add_status_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Add a callback for status changes."""
        with self._callbacks_lock:
            self._status_callbacks.add(callback)

    def remove_status_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Remove a status callback."""
        with self._callbacks_lock:
            self._status_callbacks.discard(callback)

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    def _check_lock(self) -> bool:
        """Check if another agent is already running for this project."""
        if not self.lock_file.exists():
            return True

        try:
            pid = int(self.lock_file.read_text().strip())
            if psutil.pid_exists(pid):
                # Check if it's actually our agent process
                try:
                    proc = psutil.Process(pid)
                    cmdline = " ".join(proc.cmdline())
                    if "autonomous_agent_demo.py" in cmdline:
                        return False  # Another agent is running
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Stale lock file
            self.lock_file.unlink(missing_ok=True)
            return True
        except (ValueError, OSError):
            self.lock_file.unlink(missing_ok=True)
            return True

    def _create_lock(self) -> None:
        """Create lock file with current process PID."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        if self.process:
            self.lock_file.write_text(str(self.process.pid))

    def _remove_lock(self) -> None:
        """Remove lock file."""
        self.lock_file.unlink(missing_ok=True)

    async def _broadcast_output(self, line: str) -> None:
        """Broadcast output line to all registered callbacks."""
        with self._callbacks_lock:
            callbacks = list(self._output_callbacks)

        for callback in callbacks:
            await self._safe_callback(callback, line)

    async def _stream_output(self) -> None:
        """Stream process output to callbacks."""
        if not self.process or not self.process.stdout:
            return

        try:
            loop = asyncio.get_running_loop()
            while True:
                # Use run_in_executor for blocking readline
                line = await loop.run_in_executor(
                    None, self.process.stdout.readline
                )
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").rstrip()
                sanitized = sanitize_output(decoded)

                await self._broadcast_output(sanitized)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Output streaming error: {e}")
        finally:
            # Check if process ended
            if self.process and self.process.poll() is not None:
                exit_code = self.process.returncode
                if exit_code != 0 and self.status == "running":
                    self.status = "crashed"
                elif self.status == "running":
                    self.status = "stopped"
                self._remove_lock()

    def _has_docker_compose(self) -> bool:
        """Check if project has docker-compose configuration."""
        compose_files = [
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ]
        return any((self.project_dir / f).exists() for f in compose_files)

    async def _start_docker_containers(self) -> tuple[bool, str]:
        """
        Start Docker containers if docker-compose.yml exists.

        Returns:
            Tuple of (success, message)
        """
        if not self._has_docker_compose():
            return True, "No docker-compose.yml found, skipping container startup"

        try:
            logger.info(f"Starting Docker containers for {self.project_name}")

            # Run docker compose up -d
            result = subprocess.run(
                ["docker", "compose", "up", "-d", "--build"],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for build
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.warning(f"Docker compose failed: {error_msg}")
                # Don't block agent start, just warn
                return True, f"Warning: Docker compose failed: {error_msg[:200]}"

            logger.info(f"Docker containers started for {self.project_name}")
            return True, "Docker containers started"

        except subprocess.TimeoutExpired:
            return True, "Warning: Docker compose timed out, containers may not be ready"
        except FileNotFoundError:
            return True, "Warning: Docker not found, skipping container startup"
        except Exception as e:
            logger.warning(f"Error starting Docker containers: {e}")
            return True, f"Warning: Could not start Docker containers: {e}"

    async def _stop_docker_containers(self) -> None:
        """Stop Docker containers if they were started."""
        if not self._has_docker_compose():
            return

        try:
            logger.info(f"Stopping Docker containers for {self.project_name}")
            subprocess.run(
                ["docker", "compose", "down"],
                cwd=str(self.project_dir),
                capture_output=True,
                timeout=60,
            )
        except Exception as e:
            logger.warning(f"Error stopping Docker containers: {e}")

    async def start(
        self,
        yolo_mode: bool = False,
        auto_start_docker: bool = True,
        mode: str | None = None,
        model: str | None = None,
    ) -> tuple[bool, str]:
        """
        Start the agent as a subprocess.

        Args:
            yolo_mode: If True, run in YOLO mode (no browser testing)
            auto_start_docker: If True, start Docker containers before agent

        Returns:
            Tuple of (success, message)
        """
        if self.status in ("running", "paused"):
            return False, f"Agent is already {self.status}"

        if not self._check_lock():
            return False, "Another agent instance is already running for this project"

        # Start Docker containers if configured
        if auto_start_docker:
            docker_success, docker_msg = await self._start_docker_containers()
            if docker_msg:
                logger.info(docker_msg)

        # Store mode for status queries
        self.yolo_mode = yolo_mode
        self.mode = mode
        self.model = model

        # Build command - pass absolute path to project directory
        cmd = [
            sys.executable,
            str(self.root_dir / "autonomous_agent_demo.py"),
            "--project-dir",
            str(self.project_dir.resolve()),
        ]

        # Add --yolo flag if YOLO mode is enabled
        if yolo_mode:
            cmd.append("--yolo")

        if mode:
            cmd.extend(["--mode", mode])

        if model:
            cmd.extend(["--model", model])

        try:
            # Start subprocess with piped stdout/stderr
            # Use project_dir as cwd so Claude SDK sandbox allows access to project files
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.project_dir),
            )

            self._create_lock()
            self.started_at = datetime.now()
            self.status = "running"

            # Start output streaming task
            self._output_task = asyncio.create_task(self._stream_output())

            return True, f"Agent started with PID {self.process.pid}"
        except Exception as e:
            logger.exception("Failed to start agent")
            return False, f"Failed to start agent: {e}"

    async def stop(self) -> tuple[bool, str]:
        """
        Stop the agent (SIGTERM then SIGKILL if needed).

        Returns:
            Tuple of (success, message)
        """
        if not self.process or self.status == "stopped":
            return False, "Agent is not running"

        try:
            # Cancel output streaming
            if self._output_task:
                self._output_task.cancel()
                try:
                    await self._output_task
                except asyncio.CancelledError:
                    pass

            # Terminate gracefully first
            self.process.terminate()

            # Wait up to 5 seconds for graceful shutdown
            loop = asyncio.get_running_loop()
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, self.process.wait),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # Force kill if still running
                self.process.kill()
                await loop.run_in_executor(None, self.process.wait)

            self._remove_lock()
            self.status = "stopped"
            self.process = None
            self.started_at = None
            self.yolo_mode = False  # Reset YOLO mode
            self.mode = None

            return True, "Agent stopped"
        except Exception as e:
            logger.exception("Failed to stop agent")
            return False, f"Failed to stop agent: {e}"

    async def pause(self) -> tuple[bool, str]:
        """
        Pause the agent using psutil for cross-platform support.

        Returns:
            Tuple of (success, message)
        """
        if not self.process or self.status != "running":
            return False, "Agent is not running"

        try:
            proc = psutil.Process(self.process.pid)
            proc.suspend()
            self.status = "paused"
            return True, "Agent paused"
        except psutil.NoSuchProcess:
            self.status = "crashed"
            self._remove_lock()
            return False, "Agent process no longer exists"
        except Exception as e:
            logger.exception("Failed to pause agent")
            return False, f"Failed to pause agent: {e}"

    async def resume(self) -> tuple[bool, str]:
        """
        Resume a paused agent.

        Returns:
            Tuple of (success, message)
        """
        if not self.process or self.status != "paused":
            return False, "Agent is not paused"

        try:
            proc = psutil.Process(self.process.pid)
            proc.resume()
            self.status = "running"
            return True, "Agent resumed"
        except psutil.NoSuchProcess:
            self.status = "crashed"
            self._remove_lock()
            return False, "Agent process no longer exists"
        except Exception as e:
            logger.exception("Failed to resume agent")
            return False, f"Failed to resume agent: {e}"

    async def healthcheck(self) -> bool:
        """
        Check if the agent process is still alive.

        Updates status to 'crashed' if process has died unexpectedly.

        Returns:
            True if healthy, False otherwise
        """
        if not self.process:
            return self.status == "stopped"

        poll = self.process.poll()
        if poll is not None:
            # Process has terminated
            if self.status in ("running", "paused"):
                self.status = "crashed"
                self._remove_lock()
            return False

        return True

    def get_status_dict(self) -> dict:
        """Get current status as a dictionary."""
        return {
            "status": self.status,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "yolo_mode": self.yolo_mode,
            "mode": self.mode,
        }


# Global registry of process managers per project with thread safety
_managers: dict[str, AgentProcessManager] = {}
_managers_lock = threading.Lock()

def check_agent_lock(project_dir: Path) -> tuple[bool, bool]:
    """
    Check whether an agent lock is active and clear stale locks.

    Returns:
        (is_running, lock_cleared)
    """
    lock_file = project_dir / ".agent.lock"
    if not lock_file.exists():
        return False, False

    try:
        pid = int(lock_file.read_text().strip())
    except (ValueError, OSError):
        lock_file.unlink(missing_ok=True)
        return False, True

    if not psutil.pid_exists(pid):
        lock_file.unlink(missing_ok=True)
        return False, True

    try:
        proc = psutil.Process(pid)
        cmdline = " ".join(proc.cmdline())
        if "autonomous_agent_demo.py" not in cmdline:
            lock_file.unlink(missing_ok=True)
            return False, True
    except psutil.NoSuchProcess:
        lock_file.unlink(missing_ok=True)
        return False, True
    except psutil.AccessDenied:
        # Unable to verify, assume running to be safe
        return True, False

    return True, False


def get_manager(project_name: str, project_dir: Path, root_dir: Path) -> AgentProcessManager:
    """Get or create a process manager for a project (thread-safe).

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory
        root_dir: Root directory of the autonomous-coding-ui project
    """
    with _managers_lock:
        if project_name not in _managers:
            _managers[project_name] = AgentProcessManager(project_name, project_dir, root_dir)
        return _managers[project_name]


async def cleanup_all_managers() -> None:
    """Stop all running agents. Called on server shutdown."""
    with _managers_lock:
        managers = list(_managers.values())

    for manager in managers:
        try:
            if manager.status != "stopped":
                await manager.stop()
        except Exception as e:
            logger.warning(f"Error stopping manager for {manager.project_name}: {e}")

    with _managers_lock:
        _managers.clear()
