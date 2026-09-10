from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence

from .models import CommandResult


class CommandRunner:
    """Run host commands without invoking a shell."""

    def run(self, argv: Sequence[str], timeout: float = 30.0) -> CommandResult:
        command = [str(item) for item in argv]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return CommandResult(
                argv=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_s=time.monotonic() - started,
            )
        except FileNotFoundError as exc:
            return CommandResult(
                argv=command,
                returncode=None,
                stderr=str(exc),
                duration_s=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            return CommandResult(
                argv=command,
                returncode=None,
                stdout=stdout,
                stderr=stderr,
                duration_s=time.monotonic() - started,
                timed_out=True,
            )
