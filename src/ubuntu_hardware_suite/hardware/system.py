from __future__ import annotations

import time

from ..models import CheckResult, Evidence, HardwareInventory
from .test import CheckFunction, HardwareTest


class SystemTest(HardwareTest):
    category = "system"

    def checks(self) -> dict[str, CheckFunction]:
        return {
            "host.os": self.check_host_os,
            "host.kernel": self.check_kernel,
        }

    def check_host_os(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        distro = inventory.os_release.get("ID", "").lower()
        version = inventory.os_release.get("VERSION_ID", "")
        evidence = [Evidence("os-release", inventory.os_release)]
        linux_skip = self.linux_skip(
            inventory,
            "host.os",
            "Ubuntu host operating system",
            started,
        )
        if linux_skip:
            linux_skip.evidence = evidence
            return linux_skip
        if distro != "ubuntu":
            return self.result(
                "host.os",
                "Ubuntu host operating system",
                "fail",
                f"Detected distribution {distro or 'unknown'}, expected Ubuntu.",
                evidence=evidence,
                started=started,
            )
        return self.result(
            "host.os",
            "Ubuntu host operating system",
            "pass",
            f"Ubuntu {version or 'version unknown'} detected.",
            evidence=evidence,
            started=started,
        )

    def check_kernel(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        kernel = inventory.platform.get("release", "")
        linux_skip = self.linux_skip(
            inventory,
            "host.kernel",
            "Linux kernel present",
            started,
        )
        if linux_skip:
            linux_skip.evidence = [Evidence("platform.release", kernel)]
            return linux_skip
        if not kernel:
            return self.result(
                "host.kernel",
                "Linux kernel present",
                "fail",
                "The running kernel version could not be collected.",
                started=started,
            )
        return self.result(
            "host.kernel",
            "Linux kernel present",
            "pass",
            f"Running kernel {kernel}.",
            evidence=[Evidence("platform.release", kernel)],
            started=started,
        )