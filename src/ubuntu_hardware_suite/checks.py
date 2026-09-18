from __future__ import annotations

from collections.abc import Callable

from .hardware import build_check_registry
from .models import CheckResult, HardwareInventory

CheckFunction = Callable[[HardwareInventory], CheckResult]

CHECKS: dict[str, CheckFunction] = build_check_registry()

# Backward-compatible function names for existing callers and tests.
check_host_os = CHECKS["host.os"]
check_kernel = CHECKS["host.kernel"]
check_cpu_topology = CHECKS["cpu.topology"]
check_cpu_frequency = CHECKS["cpu.frequency"]
check_cpu_cstates = CHECKS["cpu.cstates"]
check_cpu_stress = CHECKS["cpu.stress"]
check_pci_driver_binding = CHECKS["pci.driver_binding"]
check_network_link = CHECKS["network.link"]
check_storage_root = CHECKS["storage.root"]
check_render_device = CHECKS["gpu.render_device"]
check_nvidia_gpu = CHECKS["gpu.nvidia"]


def available_checks() -> list[tuple[str, str]]:
    return sorted(
        (check_id, check_id.replace(".", " ").replace("_", " "))
        for check_id in CHECKS
    )