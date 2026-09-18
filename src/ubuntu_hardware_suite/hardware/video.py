from __future__ import annotations

import os
import time

from ..models import CheckResult, Evidence, HardwareInventory
from .test import CheckFunction, HardwareTest


class VideoTest(HardwareTest):
    category = "video"

    def checks(self) -> dict[str, CheckFunction]:
        return {
            "gpu.render_device": self.check_render_device,
            "gpu.nvidia": self.check_nvidia_gpu,
        }

    def check_render_device(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        gpu_present = any(
            any(
                token in device.get("name", "").lower()
                for token in ("vga", "3d controller", "display")
            )
            for device in inventory.pci_devices
        )
        render_nodes = [
            entry
            for entry in ("/dev/dri/renderD128", "/dev/dri/card0")
            if os.path.exists(entry)
        ]
        if not gpu_present:
            return self.result(
                "gpu.render_device",
                "GPU render device is exposed",
                "skip",
                "No PCI display controller was reported.",
                started=started,
            )
        if render_nodes:
            return self.result(
                "gpu.render_device",
                "GPU render device is exposed",
                "pass",
                "The kernel exposed a DRM device node.",
                evidence=[Evidence("drm.nodes", render_nodes)],
                started=started,
            )
        return self.result(
            "gpu.render_device",
            "GPU render device is exposed",
            "fail",
            "A display controller was found, but no DRM device node is visible.",
            started=started,
        )

    def check_nvidia_gpu(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        nvidia_devices = [
            device
            for device in inventory.pci_devices
            if "nvidia" in device.get("name", "").lower()
        ]
        if not nvidia_devices:
            return self.result(
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
            return self.result(
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
            return self.result(
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
            return self.result(
                "gpu.nvidia",
                "NVIDIA GPU driver compatibility",
                "fail",
                "The nvidia kernel driver is bound, but nvidia-smi is unavailable.",
                details=command.stderr if command else "nvidia-smi was not collected.",
                evidence=evidence,
                started=started,
            )
        if command.returncode != 0 or not inventory.nvidia_gpus:
            return self.result(
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
        return self.result(
            "gpu.nvidia",
            "NVIDIA GPU driver compatibility",
            "pass",
            f"nvidia-smi successfully queried {len(inventory.nvidia_gpus)} GPU(s): {names}.",
            evidence=evidence,
            started=started,
        )