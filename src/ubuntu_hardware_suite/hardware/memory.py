from __future__ import annotations

from .test import CheckFunction, HardwareTest


class MemoryTest(HardwareTest):
    category = "memory"

    def checks(self) -> dict[str, CheckFunction]:
        # Reserved for future memory inventory and stress checks.
        return {}