from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Status = Literal["pass", "fail", "skip", "error"]


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    source: str
    value: Any
    redacted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckResult:
    check_id: str
    title: str
    status: Status
    summary: str
    details: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
            "evidence": [item.to_dict() for item in self.evidence],
            "duration_s": self.duration_s,
        }


@dataclass
class HardwareInventory:
    collected_at: str
    platform: dict[str, Any]
    os_release: dict[str, str]
    commands: dict[str, CommandResult]
    pci_devices: list[dict[str, Any]] = field(default_factory=list)
    usb_devices: list[dict[str, Any]] = field(default_factory=list)
    block_devices: dict[str, Any] = field(default_factory=dict)
    network_links: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["commands"] = {
            name: result.to_dict() for name, result in self.commands.items()
        }
        return data


@dataclass
class SuiteReport:
    schema_version: str
    suite: str
    plan: dict[str, Any]
    started_at: str
    finished_at: str
    host: HardwareInventory
    results: list[CheckResult]

    def to_dict(self) -> dict[str, Any]:
        counts = {status: 0 for status in ("pass", "fail", "skip", "error")}
        for result in self.results:
            counts[result.status] += 1
        return {
            "schema_version": self.schema_version,
            "suite": self.suite,
            "plan": self.plan,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "host": self.host.to_dict(),
            "summary": {
                "total": len(self.results),
                **counts,
            },
            "results": [result.to_dict() for result in self.results],
        }
