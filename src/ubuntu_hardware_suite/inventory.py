from __future__ import annotations

import datetime as dt
import json
import platform
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import CommandResult, HardwareInventory
from .runner import CommandRunner

CPU_SYSFS = Path("/sys/devices/system/cpu")
NODE_SYSFS = Path("/sys/devices/system/node")
EDAC_SYSFS = Path("/sys/devices/system/edac/mc")
CLOCKSOURCE_SYSFS = Path("/sys/devices/system/clocksource/clocksource0")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_os_release(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def parse_meminfo(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parts = value.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0])
        except ValueError:
            continue
    return values


def parse_cpuinfo(text: str) -> dict[str, Any]:
    identity: dict[str, Any] = {}
    microcodes: list[str] = []
    flags: set[str] = set()
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "vendor_id" and "vendor_id" not in identity:
            identity["vendor_id"] = value
        elif key == "model name" and "model_name" not in identity:
            identity["model_name"] = value
        elif key == "Hardware" and "model_name" not in identity:
            identity["model_name"] = value
        elif key == "microcode" and value:
            microcodes.append(value)
        elif key in {"flags", "Features"}:
            flags.update(value.split())
    identity["microcodes"] = microcodes
    identity["flags"] = sorted(flags)
    return identity


def parse_lspci(text: str) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        if line and not line[0].isspace():
            if current:
                devices.append(current)
            address, _, name = line.partition(" ")
            current = {
                "address": address,
                "name": name.strip(),
                "driver": None,
                "modules": [],
                "raw": [line],
            }
            continue
        if current is None:
            continue
        current["raw"].append(line)
        stripped = line.strip()
        if stripped.startswith("Kernel driver in use:"):
            current["driver"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Kernel modules:"):
            current["modules"] = [
                item.strip()
                for item in stripped.split(":", 1)[1].split(",")
                if item.strip()
            ]
    if current:
        devices.append(current)
    return devices


def parse_json_command(result: CommandResult) -> Any:
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def parse_nvidia_smi(text: str) -> list[dict[str, str]]:
    """Parse the stable CSV output requested from nvidia-smi."""
    gpus: list[dict[str, str]] = []
    fields = (
        "name",
        "driver_version",
        "pci_bus_id",
        "memory_total_mib",
        "temperature_gpu_c",
    )
    for line in text.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) != len(fields):
            continue
        gpus.append(dict(zip(fields, values)))
    return gpus


def parse_lscpu_json(text: str) -> dict[str, str]:
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    fields: dict[str, str] = {}
    for item in data.get("lscpu", []):
        key = str(item.get("field", "")).rstrip(":")
        value = str(item.get("data", "")).strip()
        if key:
            fields[key] = value
    return fields


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def collect_keyed_text(directory: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return values
    for entry in entries:
        if entry.is_file():
            value = _read_text(entry)
            if value is not None:
                values[entry.name] = value
    return values


def collect_cpu_frequencies(
    root: Path = CPU_SYSFS,
) -> list[dict[str, Any]]:
    frequencies: list[dict[str, Any]] = []
    for cpu_path in sorted(root.glob("cpu[0-9]*")):
        cpufreq = cpu_path / "cpufreq"
        if not cpufreq.exists():
            continue
        item = {"cpu": cpu_path.name}
        for field in (
            "scaling_driver",
            "scaling_governor",
            "scaling_available_governors",
            "scaling_cur_freq",
            "scaling_min_freq",
            "scaling_max_freq",
            "cpuinfo_min_freq",
            "cpuinfo_max_freq",
        ):
            value = _read_text(cpufreq / field)
            if value is not None:
                item[field] = value
        frequencies.append(item)
    return frequencies


def collect_cpu_idle_states(
    root: Path = CPU_SYSFS,
) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for cpu_path in sorted(root.glob("cpu[0-9]*")):
        cpuidle = cpu_path / "cpuidle"
        if not cpuidle.exists():
            continue
        for state_path in sorted(cpuidle.glob("state[0-9]*")):
            item = {"cpu": cpu_path.name, "state": state_path.name}
            for field in ("name", "desc", "disable", "latency", "residency", "usage", "time"):
                value = _read_text(state_path / field)
                if value is not None:
                    item[field] = value
            states.append(item)
    return states


def collect_cpu_topology(root: Path = CPU_SYSFS) -> list[dict[str, Any]]:
    topology: list[dict[str, Any]] = []
    for cpu_path in sorted(root.glob("cpu[0-9]*")):
        topo = cpu_path / "topology"
        if not topo.exists():
            continue
        item = {"cpu": cpu_path.name}
        for field in (
            "physical_package_id",
            "core_id",
            "thread_siblings_list",
            "core_siblings_list",
        ):
            value = _read_text(topo / field)
            if value is not None:
                item[field] = value
        topology.append(item)
    return topology


def collect_cpu_cache(root: Path = CPU_SYSFS) -> list[dict[str, Any]]:
    cache: list[dict[str, Any]] = []
    cache_root = root / "cpu0" / "cache"
    for index_path in sorted(cache_root.glob("index*")):
        item = {"index": index_path.name}
        for field in ("level", "type", "size", "coherency_line_size", "shared_cpu_list"):
            value = _read_text(index_path / field)
            if value is not None:
                item[field] = value
        cache.append(item)
    return cache


def collect_cpu_numa(root: Path = NODE_SYSFS) -> dict[str, Any]:
    online = _read_text(root / "online")
    if online is None:
        return {}
    nodes: list[dict[str, str]] = []
    for node_path in sorted(root.glob("node[0-9]*")):
        cpulist = _read_text(node_path / "cpulist")
        item = {"node": node_path.name}
        if cpulist is not None:
            item["cpulist"] = cpulist
        nodes.append(item)
    return {"online": online, "nodes": nodes}


def collect_cpu_clocksource(root: Path = CLOCKSOURCE_SYSFS) -> dict[str, str]:
    values: dict[str, str] = {}
    current = _read_text(root / "current_clocksource")
    available = _read_text(root / "available_clocksource")
    if current is not None:
        values["current"] = current
    if available is not None:
        values["available"] = available
    return values


def collect_edac_counters(root: Path = EDAC_SYSFS) -> list[dict[str, Any]]:
    counters: list[dict[str, Any]] = []
    for mc_path in sorted(root.glob("mc[0-9]*")):
        item = {"controller": mc_path.name}
        for field in ("ce_count", "ue_count"):
            value = _read_text(mc_path / field)
            if value is not None:
                item[field] = value
        counters.append(item)
    return counters


def collect_thermal_throttle_counts(root: Path = CPU_SYSFS) -> list[dict[str, Any]]:
    counters: list[dict[str, Any]] = []
    for cpu_path in sorted(root.glob("cpu[0-9]*")):
        thermal = cpu_path / "thermal_throttle"
        if not thermal.exists():
            continue
        item = {"cpu": cpu_path.name}
        for field in ("core_throttle_count", "package_throttle_count"):
            value = _read_text(thermal / field)
            if value is not None:
                item[field] = value
        counters.append(item)
    return counters


def collect_inventory(
    runner: CommandRunner | None = None,
    timeout: float = 20.0,
    requested_checks: Iterable[str] | None = None,
) -> HardwareInventory:
    runner = runner or CommandRunner()
    requested = set(requested_checks or [])
    commands = {
        "os_release": runner.run(["cat", "/etc/os-release"], timeout=timeout),
        "cpu": runner.run(["lscpu", "-J"], timeout=timeout),
        "cpuinfo": runner.run(["cat", "/proc/cpuinfo"], timeout=timeout),
        "meminfo": runner.run(["cat", "/proc/meminfo"], timeout=timeout),
        "pci": runner.run(["lspci", "-nnk"], timeout=timeout),
        "usb": runner.run(["lsusb"], timeout=timeout),
        "block": runner.run(["lsblk", "-J", "-o", "NAME,TYPE,FSTYPE,MOUNTPOINTS,SIZE"], timeout=timeout),
        "links": runner.run(["ip", "-j", "link"], timeout=timeout),
        "nvidia_smi": runner.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,pci.bus_id,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            timeout=timeout,
        ),
    }
    if "cpu.stress" in requested:
        commands["cpu_stress"] = runner.run(
            [
                "stress-ng",
                "--cpu",
                "0",
                "--timeout",
                "30s",
                "--metrics-brief",
                "--verify",
            ],
            timeout=max(timeout, 45.0),
        )
    if "ras.mce" in requested:
        commands["kernel_log"] = runner.run(
            ["journalctl", "-k", "--no-pager"],
            timeout=max(timeout, 45.0),
        )
    parsed_links = parse_json_command(commands["links"])
    cpu_identity = parse_cpuinfo(commands["cpuinfo"].stdout)
    return HardwareInventory(
        collected_at=_utc_now(),
        platform={
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        os_release=parse_os_release(commands["os_release"].stdout),
        commands=commands,
        pci_devices=parse_lspci(commands["pci"].stdout),
        usb_devices=[
            {"raw": line}
            for line in commands["usb"].stdout.splitlines()
            if line.strip()
        ],
        block_devices=parse_json_command(commands["block"]),
        network_links=parsed_links if isinstance(parsed_links, list) else [],
        nvidia_gpus=parse_nvidia_smi(commands["nvidia_smi"].stdout),
        cpu_info=parse_lscpu_json(commands["cpu"].stdout),
        cpu_frequencies=collect_cpu_frequencies(),
        cpu_idle_states=collect_cpu_idle_states(),
        cpu_identity=cpu_identity,
        mem_info=parse_meminfo(commands["meminfo"].stdout),
        cpu_microcodes=cpu_identity.get("microcodes", []),
        cpu_vulnerabilities=collect_keyed_text(CPU_SYSFS / "vulnerabilities"),
        cpu_topology=collect_cpu_topology(),
        cpu_cache=collect_cpu_cache(),
        cpu_numa=collect_cpu_numa(),
        cpu_clocksource=collect_cpu_clocksource(),
        edac_counters=collect_edac_counters(),
        thermal_throttle_counts=collect_thermal_throttle_counts(),
    )