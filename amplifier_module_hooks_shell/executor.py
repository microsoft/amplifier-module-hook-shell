"""
Hook executor for running shell commands.

Executes Claude Code hooks as subprocesses with proper I/O handling.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any


class HookExecutor:
    """Execute Claude Code hooks as shell commands."""

    def __init__(self, project_dir: Path, hooks_dir: Path, session_id: str):
        """
        Initialize executor.

        Args:
            project_dir: Project root directory
            hooks_dir: Hooks directory (.amplifier/hooks/)
            session_id: Current session ID
        """
        self.project_dir = project_dir
        self.hooks_dir = hooks_dir
        self.session_id = session_id

    async def execute(
        self, command: str, input_data: dict[str, Any], timeout: float = 30.0
    ) -> tuple[int, str, str]:
        """
        Execute a hook command.

        Args:
            command: Shell command to execute
            input_data: JSON data to pass on stdin
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        # Prepare environment variables
        env = self._prepare_environment()

        # Expand environment variables in command
        expanded_command = os.path.expandvars(command)

        # Create subprocess
        proc = await asyncio.create_subprocess_shell(
            expanded_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(self.project_dir),
        )

        # Prepare input JSON
        input_json = json.dumps(input_data).encode("utf-8")

        try:
            # Execute with timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_json), timeout=timeout
            )

            return (
                proc.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )

        except asyncio.TimeoutError:
            # Kill the process on timeout
            proc.kill()
            await proc.wait()
            return (1, "", f"Hook timed out after {timeout}s")

        except Exception as e:
            return (1, "", f"Hook execution failed: {str(e)}")

    def _prepare_environment(self) -> dict[str, str]:
        """
        Prepare environment variables for hook execution.

        Returns:
            Environment dictionary with Amplifier variables
        """
        env = os.environ.copy()

        # Amplifier variables
        env["AMPLIFIER_PROJECT_DIR"] = str(self.project_dir)
        env["AMPLIFIER_HOOKS_DIR"] = str(self.hooks_dir)
        env["AMPLIFIER_SESSION_ID"] = self.session_id

        # Claude Code compatibility aliases
        env["CLAUDE_PROJECT_DIR"] = str(self.project_dir)

        return env
