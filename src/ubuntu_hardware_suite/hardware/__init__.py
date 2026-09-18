from __future__ import annotations

from collections.abc import Iterable

from .cpu import CpuTest
from .memory import MemoryTest
from .network import NetworkTest
from .pci import PciTest
from .storage import StorageTest
from .system import SystemTest
from .test import CheckFunction, HardwareTest
from .video import VideoTest


def hardware_tests() -> list[HardwareTest]:
    return [
        SystemTest(),
        CpuTest(),
        PciTest(),
        NetworkTest(),
        StorageTest(),
        VideoTest(),
        MemoryTest(),
    ]


def build_check_registry(
    tests: Iterable[HardwareTest] | None = None,
) -> dict[str, CheckFunction]:
    registry: dict[str, CheckFunction] = {}
    for hardware_test in tests or hardware_tests():
        for check_id, check in hardware_test.checks().items():
            if check_id in registry:
                raise ValueError(f"duplicate check id: {check_id}")
            registry[check_id] = check
    return registry