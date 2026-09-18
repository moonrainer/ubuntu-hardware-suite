from __future__ import annotations

import time

from ..models import CheckResult, Evidence, HardwareInventory
from .test import CheckFunction, HardwareTest


class StorageTest(HardwareTest):
    category = "storage"

    def checks(self) -> dict[str, CheckFunction]:
        return {"storage.root": self.check_root}

    def check_root(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        devices = inventory.block_devices.get("blockdevices", [])
        if not devices:
            return self.result(
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
            return self.result(
                "storage.root",
                "Root storage is visible",
                "pass",
                "A block device is mounted at the root filesystem.",
                evidence=evidence,
                started=started,
            )
        return self.result(
            "storage.root",
            "Root storage is visible",
            "fail",
            "No root filesystem mount was found in lsblk output.",
            evidence=evidence,
            started=started,
        )