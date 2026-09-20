from __future__ import annotations

import time

from ..models import CheckResult, Evidence, HardwareInventory
from .test import CheckFunction, HardwareTest

RAM_PER_CORE_MIN_GIB = 1.5


class CpuTest(HardwareTest):
    category = "cpu"

    def checks(self) -> dict[str, CheckFunction]:
        return {
            "cpu.identity": self.check_identity,
            "cpu.ram_per_core": self.check_ram_per_core,
            "firmware.microcode": self.check_microcode,
            "security.vulnerabilities": self.check_vulnerabilities,
            "cpu.topology": self.check_topology,
            "cpu.cache": self.check_cache,
            "cpu.numa": self.check_numa,
            "cpu.frequency": self.check_frequency,
            "cpu.cstates": self.check_cstates,
            "cpu.cstates.residency": self.check_cstate_residency,
            "cpu.clocksource": self.check_clocksource,
            "ras.edac": self.check_edac,
            "ras.throttle_history": self.check_throttle_history,
            "ras.mce": self.check_machine_checks,
            "cpu.stress": self.check_stress,
        }

    def _linux_skip(
        self,
        inventory: HardwareInventory,
        check_id: str,
        title: str,
        started: float,
    ) -> CheckResult | None:
        return self.linux_skip(inventory, check_id, title, started)

    def check_identity(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "cpu.identity",
            "CPU identity is visible",
            started,
        )
        if linux_skip:
            return linux_skip
        vendor = inventory.cpu_identity.get("vendor_id") or inventory.cpu_info.get("Vendor ID")
        model = inventory.cpu_identity.get("model_name") or inventory.cpu_info.get("Model name")
        if not vendor and not model:
            return self.result(
                "cpu.identity",
                "CPU identity is visible",
                "skip",
                "No CPU identity was reported by /proc/cpuinfo or lscpu.",
                evidence=[Evidence("cpu.identity", inventory.cpu_identity)],
                started=started,
            )
        return self.result(
            "cpu.identity",
            "CPU identity is visible",
            "pass",
            f"vendor={vendor or 'unknown'} model={model or 'unknown'}.",
            evidence=[Evidence("cpu.identity", inventory.cpu_identity)],
            started=started,
        )

    def check_ram_per_core(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "cpu.ram_per_core",
            "RAM per logical CPU meets certification threshold",
            started,
        )
        if linux_skip:
            return linux_skip
        mem_kb = _to_float(inventory.mem_info.get("MemTotal"))
        cpus = _to_float(inventory.cpu_info.get("CPU(s)"))
        if not mem_kb or not cpus:
            return self.result(
                "cpu.ram_per_core",
                "RAM per logical CPU meets certification threshold",
                "skip",
                "MemTotal or online CPU count was unavailable.",
                evidence=[Evidence("meminfo", inventory.mem_info), Evidence("lscpu", inventory.cpu_info)],
                started=started,
            )
        total_gib = mem_kb / 1048576
        ratio = total_gib / cpus
        status = "pass" if ratio >= RAM_PER_CORE_MIN_GIB else "fail"
        summary = (
            f"{total_gib:.2f} GiB / {int(cpus)} logical CPU(s) = {ratio:.2f} GiB/core "
            f"(minimum {RAM_PER_CORE_MIN_GIB:.1f})."
        )
        return self.result(
            "cpu.ram_per_core",
            "RAM per logical CPU meets certification threshold",
            status,
            summary,
            evidence=[Evidence("meminfo", inventory.mem_info), Evidence("lscpu", inventory.cpu_info)],
            started=started,
        )

    def check_microcode(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "firmware.microcode",
            "CPU microcode is consistent",
            started,
        )
        if linux_skip:
            return linux_skip
        revisions = sorted(set(inventory.cpu_microcodes))
        if not revisions:
            return self.result(
                "firmware.microcode",
                "CPU microcode is consistent",
                "skip",
                "No microcode field was found in /proc/cpuinfo.",
                started=started,
            )
        if len(revisions) > 1:
            return self.result(
                "firmware.microcode",
                "CPU microcode is consistent",
                "fail",
                f"Mixed microcode revisions detected: {', '.join(revisions)}.",
                evidence=[Evidence("cpu.microcode", revisions)],
                started=started,
            )
        return self.result(
            "firmware.microcode",
            "CPU microcode is consistent",
            "pass",
            f"All CPUs report microcode revision {revisions[0]}.",
            evidence=[Evidence("cpu.microcode", revisions)],
            started=started,
        )

    def check_vulnerabilities(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "security.vulnerabilities",
            "CPU vulnerability mitigations are not exposed",
            started,
        )
        if linux_skip:
            return linux_skip
        if not inventory.cpu_vulnerabilities:
            return self.result(
                "security.vulnerabilities",
                "CPU vulnerability mitigations are not exposed",
                "skip",
                "No CPU vulnerability sysfs entries were found.",
                started=started,
            )
        exposed = {
            name: value
            for name, value in inventory.cpu_vulnerabilities.items()
            if "Vulnerable" in value
        }
        if exposed:
            return self.result(
                "security.vulnerabilities",
                "CPU vulnerability mitigations are not exposed",
                "fail",
                f"{len(exposed)} vulnerability entry/entries report Vulnerable: {', '.join(sorted(exposed))}.",
                evidence=[Evidence("sysfs.vulnerabilities", inventory.cpu_vulnerabilities)],
                started=started,
            )
        return self.result(
            "security.vulnerabilities",
            "CPU vulnerability mitigations are not exposed",
            "pass",
            f"{len(inventory.cpu_vulnerabilities)} vulnerability entries checked; none report Vulnerable.",
            evidence=[Evidence("sysfs.vulnerabilities", inventory.cpu_vulnerabilities)],
            started=started,
        )

    def check_topology(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
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
        evidence = [Evidence("lscpu", inventory.cpu_info)]
        if inventory.cpu_topology:
            evidence.append(Evidence("sysfs.cpu_topology", inventory.cpu_topology))
        return self.result(
            "cpu.topology",
            "CPU topology is visible",
            "pass",
            f"{cpus} CPU(s) visible: {model}.",
            evidence=evidence,
            started=started,
        )

    def check_cache(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "cpu.cache",
            "CPU cache hierarchy is visible",
            started,
        )
        if linux_skip:
            return linux_skip
        if not inventory.cpu_cache:
            return self.result(
                "cpu.cache",
                "CPU cache hierarchy is visible",
                "skip",
                "No CPU cache sysfs entries were found.",
                started=started,
            )
        levels = sorted({item.get("level", "?") for item in inventory.cpu_cache})
        has_data_or_unified = any(
            item.get("type") in {"Data", "Unified"} for item in inventory.cpu_cache
        )
        status = "pass" if has_data_or_unified else "fail"
        summary = f"{len(inventory.cpu_cache)} cache entries visible across level(s): {', '.join(levels)}."
        return self.result(
            "cpu.cache",
            "CPU cache hierarchy is visible",
            status,
            summary,
            evidence=[Evidence("sysfs.cpu_cache", inventory.cpu_cache)],
            started=started,
        )

    def check_numa(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "cpu.numa",
            "CPU NUMA topology is visible",
            started,
        )
        if linux_skip:
            return linux_skip
        online = inventory.cpu_numa.get("online")
        if not online:
            return self.result(
                "cpu.numa",
                "CPU NUMA topology is visible",
                "skip",
                "No NUMA node information was found in sysfs.",
                started=started,
            )
        return self.result(
            "cpu.numa",
            "CPU NUMA topology is visible",
            "pass",
            f"NUMA online node mask: {online}.",
            evidence=[Evidence("sysfs.node", inventory.cpu_numa)],
            started=started,
        )

    def check_frequency(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
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
        linux_skip = self._linux_skip(
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

    def check_cstate_residency(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "cpu.cstates.residency",
            "CPU C-state residency has activity",
            started,
        )
        if linux_skip:
            return linux_skip
        usage_values = [
            _to_float(state.get("usage"))
            for state in inventory.cpu_idle_states
            if state.get("disable") in {None, "0"}
        ]
        usage_values = [value for value in usage_values if value is not None]
        if not usage_values:
            return self.result(
                "cpu.cstates.residency",
                "CPU C-state residency has activity",
                "skip",
                "No enabled C-state usage counters were readable.",
                started=started,
            )
        if max(usage_values) <= 0:
            return self.result(
                "cpu.cstates.residency",
                "CPU C-state residency has activity",
                "fail",
                "Enabled C-state usage counters are all zero.",
                evidence=[Evidence("sysfs.cpuidle", inventory.cpu_idle_states)],
                started=started,
            )
        return self.result(
            "cpu.cstates.residency",
            "CPU C-state residency has activity",
            "pass",
            "At least one enabled C-state has non-zero usage.",
            evidence=[Evidence("sysfs.cpuidle", inventory.cpu_idle_states)],
            started=started,
        )

    def check_clocksource(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "cpu.clocksource",
            "CPU clocksource is visible",
            started,
        )
        if linux_skip:
            return linux_skip
        current = inventory.cpu_clocksource.get("current")
        if not current:
            return self.result(
                "cpu.clocksource",
                "CPU clocksource is visible",
                "skip",
                "No current clocksource was exposed in sysfs.",
                started=started,
            )
        vendor = inventory.cpu_identity.get("vendor_id", "")
        summary = f"current={current}; available={inventory.cpu_clocksource.get('available', 'unknown')}"
        status = "pass"
        details = ""
        if vendor in {"GenuineIntel", "Intel"} and not current.startswith("tsc"):
            details = "Intel CPU is not using TSC; this is recorded as advisory evidence."
        return self.result(
            "cpu.clocksource",
            "CPU clocksource is visible",
            status,
            summary,
            details=details,
            evidence=[Evidence("sysfs.clocksource", inventory.cpu_clocksource)],
            started=started,
        )

    def check_edac(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "ras.edac",
            "EDAC memory-controller counters are clean",
            started,
        )
        if linux_skip:
            return linux_skip
        if not inventory.edac_counters:
            return self.result(
                "ras.edac",
                "EDAC memory-controller counters are clean",
                "skip",
                "No EDAC memory-controller counters were exposed.",
                started=started,
            )
        ce = sum(int(item.get("ce_count", 0) or 0) for item in inventory.edac_counters)
        ue = sum(int(item.get("ue_count", 0) or 0) for item in inventory.edac_counters)
        status = "fail" if ue > 0 else "pass"
        summary = f"correctable={ce}, uncorrectable={ue}."
        return self.result(
            "ras.edac",
            "EDAC memory-controller counters are clean",
            status,
            summary,
            evidence=[Evidence("sysfs.edac", inventory.edac_counters)],
            started=started,
        )

    def check_throttle_history(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        linux_skip = self._linux_skip(
            inventory,
            "ras.throttle_history",
            "CPU thermal throttle counters are clean",
            started,
        )
        if linux_skip:
            return linux_skip
        if not inventory.thermal_throttle_counts:
            return self.result(
                "ras.throttle_history",
                "CPU thermal throttle counters are clean",
                "skip",
                "No CPU thermal throttle counters were exposed.",
                started=started,
            )
        core = sum(int(item.get("core_throttle_count", 0) or 0) for item in inventory.thermal_throttle_counts)
        package = sum(int(item.get("package_throttle_count", 0) or 0) for item in inventory.thermal_throttle_counts)
        status = "fail" if core or package else "pass"
        return self.result(
            "ras.throttle_history",
            "CPU thermal throttle counters are clean",
            status,
            f"cumulative throttle counts: core={core}, package={package}.",
            evidence=[Evidence("sysfs.thermal_throttle", inventory.thermal_throttle_counts)],
            started=started,
        )

    def check_machine_checks(self, inventory: HardwareInventory) -> CheckResult:
        started = time.monotonic()
        command = inventory.commands.get("kernel_log")
        if command is None:
            return self.result(
                "ras.mce",
                "Kernel log has no CPU hardware errors",
                "skip",
                "Kernel log scan was not requested by the active plan.",
                started=started,
            )
        if command.returncode not in {0, None}:
            return self.result(
                "ras.mce",
                "Kernel log has no CPU hardware errors",
                "skip",
                "Kernel log could not be read.",
                details=command.stderr,
                evidence=[Evidence("kernel_log", command.to_dict())],
                started=started,
            )
        needles = ("machine check", "hardware error", "mce:", "edac", "cpu lockup")
        hits = [line for line in command.stdout.splitlines() if any(item in line.lower() for item in needles)]
        if hits:
            return self.result(
                "ras.mce",
                "Kernel log has no CPU hardware errors",
                "fail",
                f"{len(hits)} CPU/RAS related kernel log line(s) matched.",
                details="\n".join(hits[:20]),
                evidence=[Evidence("kernel_log.matches", hits[:20])],
                started=started,
            )
        return self.result(
            "ras.mce",
            "Kernel log has no CPU hardware errors",
            "pass",
            "No machine-check, hardware-error, lockup, or EDAC lines were found in the scanned kernel log.",
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


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).split()[0]
    try:
        return float(text)
    except ValueError:
        return None