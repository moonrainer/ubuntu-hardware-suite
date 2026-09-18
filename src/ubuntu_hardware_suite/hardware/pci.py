from __future__ import annotations

import time

from ..models import CheckResult, Evidence, HardwareInventory
from .test import CheckFunction, HardwareTest


class PciTest(HardwareTest):
    category = "pci"

    def checks(self) -> dict[str, CheckFunction]:
        return {"pci.driver_binding": self.check_driver_binding}

    def check_driver_binding(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        command = inventory.commands["pci"]
        if command.returncode is None and not inventory.pci_devices:
            return self.result(
                "pci.driver_binding",
                "PCI devices have bound drivers",
                "skip",
                "lspci is unavailable or returned no device data.",
                details=command.stderr,
                started=started,
            )
        if not inventory.pci_devices:
            return self.result(
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
            return self.result(
                "pci.driver_binding",
                "PCI devices have bound drivers",
                "fail",
                f"{len(unbound)} PCI device(s) have no active kernel driver.",
                details=", ".join(unbound),
                evidence=evidence,
                started=started,
            )
        return self.result(
            "pci.driver_binding",
            "PCI devices have bound drivers",
            "pass",
            f"All {len(inventory.pci_devices)} reported PCI devices have a driver.",
            evidence=evidence,
            started=started,
        )