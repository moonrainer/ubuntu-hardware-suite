from __future__ import annotations

import time
from collections.abc import Callable

from ..models import CheckResult, Evidence, HardwareInventory, Status

CheckFunction = Callable[[HardwareInventory], CheckResult]


class HardwareTest:
    """Base class for hardware-specific compatibility checks."""

    category = "hardware"

    def checks(self) -> dict[str, CheckFunction]:
        return {}

    def result(
        self,
        check_id: str,
        title: str,
        status: Status,
        summary: str,
        details: str = "",
        evidence: list[Evidence] | None = None,
        started: float | None = None,
    ) -> CheckResult:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=status,
            summary=summary,
            details=details,
            evidence=evidence or [],
            duration_s=(time.monotonic() - started) if started else 0.0,
        )

    def linux_skip(
        self,
        inventory: HardwareInventory,
        check_id: str,
        title: str,
        started: float,
    ) -> CheckResult | None:
        if inventory.platform.get("system") == "Linux":
            return None
        return self.result(
            check_id,
            title,
            "skip",
            "Skipped because the collector is running outside Linux.",
            started=started,
        )