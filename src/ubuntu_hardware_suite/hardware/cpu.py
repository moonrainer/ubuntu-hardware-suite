from __future__ import annotations

import time

from ..models import CheckResult, Evidence, HardwareInventory
from .test import CheckFunction, HardwareTest


class CpuTest(HardwareTest):
    category = "cpu"

    def checks(self) -> dict[str, CheckFunction]:
        return {
            "cpu.topology": self.check_topology,
            "cpu.frequency": self.check_frequency,
            "cpu.cstates": self.check_cstates,
            "cpu.stress": self.check_stress,
        }

    def check_topology(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self.linux_skip(
            inventory,
            "cpu.topology",
            "CPU topology is visible",
            started,
        )
        if linux_skip:
            return linux_skip
        if not inventory.cpu_info:
            command = inventory.commands.get("cpu")
            return self.result(
                "cpu.topology",
                "CPU topology is visible",
                "skip",
                "lscpu returned no CPU topology data.",
                details=command.stderr if command else "",
                started=started,
            )
        cpus = inventory.cpu_info.get("CPU(s)", "")
        model = inventory.cpu_info.get("Model name", "unknown CPU")
        if not cpus or cpus == "0":
            return self.result(
                "cpu.topology",
                "CPU topology is visible",
                "fail",
                "No online CPU count was reported by lscpu.",
                evidence=[Evidence("lscpu", inventory.cpu_info)],
                started=started,
            )
        return self.result(
            "cpu.topology",
            "CPU topology is visible",
            "pass",
            f"{cpus} CPU(s) visible: {model}.",
            evidence=[Evidence("lscpu", inventory.cpu_info)],
            started=started,
        )

    def check_frequency(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self.linux_skip(
            inventory,
            "cpu.frequency",
            "CPU frequency scaling is visible",
            started,
        )
        if linux_skip:
            return linux_skip
        if not inventory.cpu_frequencies:
            return self.result(
                "cpu.frequency",
                "CPU frequency scaling is visible",
                "skip",
                "No cpufreq sysfs entries were found.",
                started=started,
            )
        missing_current = [
            item["cpu"]
            for item in inventory.cpu_frequencies
            if "scaling_cur_freq" not in item
        ]
        evidence = [Evidence("sysfs.cpufreq", inventory.cpu_frequencies)]
        if missing_current:
            return self.result(
                "cpu.frequency",
                "CPU frequency scaling is visible",
                "fail",
                "Some CPUs have cpufreq entries but no current frequency.",
                details=", ".join(missing_current),
                evidence=evidence,
                started=started,
            )
        governors = sorted(
            {
                item.get("scaling_governor", "unknown")
                for item in inventory.cpu_frequencies
            }
        )
        return self.result(
            "cpu.frequency",
            "CPU frequency scaling is visible",
            "pass",
            f"Frequency data is visible for {len(inventory.cpu_frequencies)} CPU(s); governors: {', '.join(governors)}.",
            evidence=evidence,
            started=started,
        )

    def check_cstates(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self.linux_skip(
            inventory,
            "cpu.cstates",
            "CPU C-states are available",
            started,
        )
        if linux_skip:
            return linux_skip
        if not inventory.cpu_idle_states:
            return self.result(
                "cpu.cstates",
                "CPU C-states are available",
                "skip",
                "No cpuidle C-state sysfs entries were found.",
                started=started,
            )
        enabled = [
            state
            for state in inventory.cpu_idle_states
            if state.get("disable") in {None, "0"}
        ]
        evidence = [Evidence("sysfs.cpuidle", inventory.cpu_idle_states)]
        if not enabled:
            return self.result(
                "cpu.cstates",
                "CPU C-states are available",
                "fail",
                "C-state entries exist, but every reported state is disabled.",
                evidence=evidence,
                started=started,
            )
        state_names = sorted(
            {
                state.get("name", state.get("state", "unknown"))
                for state in enabled
            }
        )
        return self.result(
            "cpu.cstates",
            "CPU C-states are available",
            "pass",
            f"{len(enabled)} enabled C-state entries found: {', '.join(state_names)}.",
            evidence=evidence,
            started=started,
        )

    def check_stress(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        command = inventory.commands.get("cpu_stress")
        if command is None:
            return self.result(
                "cpu.stress",
                "CPU stress smoke test",
                "skip",
                "CPU stress was not requested by the active plan.",
                started=started,
            )
        if command.returncode is None:
            return self.result(
                "cpu.stress",
                "CPU stress smoke test",
                "skip",
                "stress-ng is unavailable or timed out.",
                details=command.stderr,
                evidence=[Evidence("stress-ng", command.to_dict())],
                started=started,
            )
        if command.returncode != 0:
            return self.result(
                "cpu.stress",
                "CPU stress smoke test",
                "fail",
                "stress-ng reported a CPU stress failure.",
                details=command.stderr or command.stdout,
                evidence=[Evidence("stress-ng", command.to_dict())],
                started=started,
            )
        return self.result(
            "cpu.stress",
            "CPU stress smoke test",
            "pass",
            "stress-ng completed a verified 30 second CPU stress run.",
            evidence=[Evidence("stress-ng", command.to_dict())],
            started=started,
        )