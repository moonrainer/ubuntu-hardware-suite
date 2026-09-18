from __future__ import annotations

import time

from ..models import CheckResult, Evidence, HardwareInventory
from .test import CheckFunction, HardwareTest


class NetworkTest(HardwareTest):
    category = "network"

    def checks(self) -> dict[str, CheckFunction]:
        return {"network.link": self.check_link}

    def check_link(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        if not inventory.network_links:
            return self.result(
                "network.link",
                "Network interfaces are visible",
                "skip",
                "The ip utility returned no JSON link data.",
                started=started,
            )
        usable = [
            link
            for link in inventory.network_links
            if link.get("ifname") != "lo"
            and link.get("operstate") in {"UP", "UNKNOWN"}
        ]
        if usable:
            return self.result(
                "network.link",
                "Network interfaces are visible",
                "pass",
                f"{len(usable)} non-loopback interface(s) are visible and usable.",
                evidence=[Evidence("ip.link", inventory.network_links)],
                started=started,
            )
        return self.result(
            "network.link",
            "Network interfaces are visible",
            "fail",
            "No non-loopback interface is in an operationally usable state.",
            evidence=[Evidence("ip.link", inventory.network_links)],
            started=started,
        )