from __future__ import annotations

import os
import time
from collections.abc import Callable

from .models import CheckResult, Evidence, HardwareInventory

CheckFunction = Callable[[HardwareInventory], CheckResult]


def _result(
    check_id: str,
    title: str,
    status: str,
    summary: str,
    details: str = "",
    evidence: list[Evidence] | None = None,
    started: float | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        title=title,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        details=details,
        evidence=evidence or [],
        duration_s=(time.monotonic() - started) if started else 0.0,
    )


def check_host_os(inventory: HardwareInventory) -> CheckResult:
    started = time.monotonic()
    distro = inventory.os_release.get("ID", "").lower()
    version = inventory.os_release.get("VERSION_ID", "")
    evidence = [Evidence("os-release", inventory.os_release)]
    if inventory.platform.get("system") != "Linux":
        return _result(
            "host.os",
            "Ubuntu host operating system",
            "skip",
            "Skipped because the collector is running outside Linux.",
            evidence=evidence,
            started=started,
        )
    if distro != "ubuntu":
        return _result(
            "host.os",
            "Ubuntu host operating system",
            "fail",
            f"Detected distribution {distro or 'unknown'}, expected Ubuntu.",
            evidence=evidence,
            started=started,
        )
    return _result(
        "host.os",
        "Ubuntu host operating system",
        "pass",
        f"Ubuntu {version or 'version unknown'} detected.",
        evidence=evidence,
        started=started,
    )


def check_kernel(inventory: HardwareInventory) -> CheckResult:
    started = time.monotonic()
    kernel = inventory.platform.get("release", "")
    if inventory.platform.get("system") != "Linux":
        return _result(
            "host.kernel",
            "Linux kernel present",
            "skip",
            "Skipped because the collector is running outside Linux.",
            evidence=[Evidence("platform.release", kernel)],
            started=started,
        )
    if not kernel:
        return _result(
            "host.kernel",
            "Linux kernel present",
            "fail",
            "The running kernel version could not be collected.",
            started=started,
        )
    return _result(
        "host.kernel",
        "Linux kernel present",
        "pass",
        f"Running kernel {kernel}.",
        evidence=[Evidence("platform.release", kernel)],
        started=started,
    )


def check_pci_driver_binding(inventory: HardwareInventory) -> CheckResult:
    started = time.monotonic()
    command = inventory.commands["pci"]
    if command.returncode is None and not inventory.pci_devices:
        return _result(
            "pci.driver_binding",
            "PCI devices have bound drivers",
            "skip",
            "lspci is unavailable or returned no device data.",
            details=command.stderr,
            started=started,
        )
    if not inventory.pci_devices:
        return _result(
            "pci.driver_binding",
            "PCI devices have bound drivers",
            "skip",
            "No PCI devices were reported.",
            started=started,
        )
    unbound = [
        device["address"]
        for device in inventory.pci_devices
        if not device.get("driver") and device.get("name", "").strip()
    ]
    evidence = [
        Evidence(
            "pci.devices",
            [
                {
                    "address": device["address"],
                    "name": device["name"],
                    "driver": device["driver"],
                    "modules": device["modules"],
                }
                for device in inventory.pci_devices
            ],
        )
    ]
    if unbound:
        return _result(
            "pci.driver_binding",
            "PCI devices have bound drivers",
            "fail",
            f"{len(unbound)} PCI device(s) have no active kernel driver.",
            details=", ".join(unbound),
            evidence=evidence,
            started=started,
        )
    return _result(
        "pci.driver_binding",
        "PCI devices have bound drivers",
        "pass",
        f"All {len(inventory.pci_devices)} reported PCI devices have a driver.",
        evidence=evidence,
        started=started,
    )


def check_network_link(inventory: HardwareInventory) -> CheckResult:
    started = time.monotonic()
    if not inventory.network_links:
        return _result(
            "network.link",
            "Network interfaces are visible",
            "skip",
            "The ip utility returned no JSON link data.",
            started=started,
        )
    usable = [
        link
        for link in inventory.network_links
        if link.get("ifname") != "lo" and link.get("operstate") in {"UP", "UNKNOWN"}
    ]
    if usable:
        return _result(
            "network.link",
            "Network interfaces are visible",
            "pass",
            f"{len(usable)} non-loopback interface(s) are visible and usable.",
            evidence=[Evidence("ip.link", inventory.network_links)],
            started=started,
        )
    return _result(
        "network.link",
        "Network interfaces are visible",
        "fail",
        "No non-loopback interface is in an operationally usable state.",
        evidence=[Evidence("ip.link", inventory.network_links)],
        started=started,
    )


def check_storage_root(inventory: HardwareInventory) -> CheckResult:
    started = time.monotonic()
    devices = inventory.block_devices.get("blockdevices", [])
    if not devices:
        return _result(
            "storage.root",
            "Root storage is visible",
            "skip",
            "lsblk returned no block-device data.",
            started=started,
        )
    mounted_root = any(
        "/" in device.get("mountpoints", [])
        for device in devices
        if isinstance(device.get("mountpoints"), list)
    )
    evidence = [Evidence("lsblk", inventory.block_devices)]
    if mounted_root:
        return _result(
            "storage.root",
            "Root storage is visible",
            "pass",
            "A block device is mounted at the root filesystem.",
            evidence=evidence,
            started=started,
        )
    return _result(
        "storage.root",
        "Root storage is visible",
        "fail",
        "No root filesystem mount was found in lsblk output.",
        evidence=evidence,
        started=started,
    )


def check_render_device(inventory: HardwareInventory) -> CheckResult:
    started = time.monotonic()
    gpu_present = any(
        any(token in device.get("name", "").lower() for token in ("vga", "3d controller", "display"))
        for device in inventory.pci_devices
    )
    render_nodes = [
        entry
        for entry in ("/dev/dri/renderD128", "/dev/dri/card0")
        if os.path.exists(entry)
    ]
    if not gpu_present:
        return _result(
            "gpu.render_device",
            "GPU render device is exposed",
            "skip",
            "No PCI display controller was reported.",
            started=started,
        )
    if render_nodes:
        return _result(
            "gpu.render_device",
            "GPU render device is exposed",
            "pass",
            "The kernel exposed a DRM device node.",
            evidence=[Evidence("drm.nodes", render_nodes)],
            started=started,
        )
    return _result(
        "gpu.render_device",
        "GPU render device is exposed",
        "fail",
        "A display controller was found, but no DRM device node is visible.",
        started=started,
    )


def check_nvidia_gpu(inventory: HardwareInventory) -> CheckResult:
    started = time.monotonic()
    nvidia_devices = [
        device
        for device in inventory.pci_devices
        if "nvidia" in device.get("name", "").lower()
    ]
    if not nvidia_devices:
        return _result(
            "gpu.nvidia",
            "NVIDIA GPU driver compatibility",
            "skip",
            "No NVIDIA PCI device was reported.",
            started=started,
        )

    evidence = [
        Evidence(
            "pci.nvidia_devices",
            [
                {
                    "address": device["address"],
                    "name": device["name"],
                    "driver": device.get("driver"),
                    "modules": device.get("modules", []),
                }
                for device in nvidia_devices
            ],
        )
    ]
    unbound = [
        device["address"]
        for device in nvidia_devices
        if not device.get("driver")
    ]
    if unbound:
        return _result(
            "gpu.nvidia",
            "NVIDIA GPU driver compatibility",
            "fail",
            "An NVIDIA GPU is present but has no active kernel driver.",
            details=", ".join(unbound),
            evidence=evidence,
            started=started,
        )

    non_nvidia_driver = [
        f"{device['address']} ({device.get('driver')})"
        for device in nvidia_devices
        if device.get("driver") != "nvidia"
    ]
    if non_nvidia_driver:
        return _result(
            "gpu.nvidia",
            "NVIDIA GPU driver compatibility",
            "fail",
            "An NVIDIA GPU is not bound to the proprietary nvidia kernel driver.",
            details=", ".join(non_nvidia_driver),
            evidence=evidence,
            started=started,
        )

    command = inventory.commands.get("nvidia_smi")
    if command is None or command.returncode is None:
        return _result(
            "gpu.nvidia",
            "NVIDIA GPU driver compatibility",
            "fail",
            "The nvidia kernel driver is bound, but nvidia-smi is unavailable.",
            details=command.stderr if command else "nvidia-smi was not collected.",
            evidence=evidence,
            started=started,
        )
    if command.returncode != 0 or not inventory.nvidia_gpus:
        return _result(
            "gpu.nvidia",
            "NVIDIA GPU driver compatibility",
            "fail",
            "nvidia-smi could not query the NVIDIA GPU.",
            details=command.stderr or command.stdout,
            evidence=evidence,
            started=started,
        )

    evidence.append(Evidence("nvidia-smi", inventory.nvidia_gpus))
    names = ", ".join(gpu["name"] for gpu in inventory.nvidia_gpus)
    return _result(
        "gpu.nvidia",
        "NVIDIA GPU driver compatibility",
        "pass",
        f"nvidia-smi successfully queried {len(inventory.nvidia_gpus)} GPU(s): {names}.",
        evidence=evidence,
        started=started,
    )

CHECKS: dict[str, CheckFunction] = {
    "host.os": check_host_os,
    "host.kernel": check_kernel,
    "pci.driver_binding": check_pci_driver_binding,
    "network.link": check_network_link,
    "storage.root": check_storage_root,
    "gpu.render_device": check_render_device,
    "gpu.nvidia": check_nvidia_gpu,
}


def available_checks() -> list[tuple[str, str]]:
    return sorted(
        (check_id, function.__name__.removeprefix("check_").replace("_", " "))
        for check_id, function in CHECKS.items()
    )
