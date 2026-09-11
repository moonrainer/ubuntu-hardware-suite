from __future__ import annotations

import datetime as dt
import json
import platform
from typing import Any

from .models import CommandResult, HardwareInventory
from .runner import CommandRunner


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

def collect_inventory(
    runner: CommandRunner | None = None,
    timeout: float = 20.0,
) -> HardwareInventory:
    runner = runner or CommandRunner()
    commands = {
        "os_release": runner.run(["cat", "/etc/os-release"], timeout=timeout),
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
    parsed_links = parse_json_command(commands["links"])
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
    )
