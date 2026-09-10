from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

from .checks import CHECKS, available_checks
from .inventory import collect_inventory
from .models import CheckResult, Evidence, SuiteReport
from .report import write_json, write_junit
from .runner import CommandRunner


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_plan(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    plan = data.get("plan", {})
    if not isinstance(plan, dict) or not isinstance(plan.get("checks"), list):
        raise ValueError("plan must contain [plan].checks as an array")
    unknown = sorted(set(plan["checks"]) - set(CHECKS))
    if unknown:
        raise ValueError(f"unknown check id(s): {', '.join(unknown)}")
    return plan


def run_plan(plan_path: Path, output_dir: Path, timeout: float) -> int:
    started_at = _utc_now()
    plan = load_plan(plan_path)
    inventory = collect_inventory(CommandRunner(), timeout=timeout)
    results: list[CheckResult] = []
    for check_id in plan["checks"]:
        started = time.monotonic()
        try:
            result = CHECKS[check_id](inventory)
        except Exception as exc:  # Keep one faulty check from hiding all evidence.
            result = CheckResult(
                check_id=check_id,
                title=check_id,
                status="error",
                summary="Check raised an unexpected exception.",
                details=f"{type(exc).__name__}: {exc}",
                evidence=[Evidence("exception", repr(exc))],
                duration_s=time.monotonic() - started,
            )
        results.append(result)
        print(f"{result.status.upper():5} {result.check_id}: {result.summary}")
    report = SuiteReport(
        schema_version="1.0",
        suite="ubuntu-hardware-suite",
        plan={"path": str(plan_path), **plan},
        started_at=started_at,
        finished_at=_utc_now(),
        host=inventory,
        results=results,
    )
    write_json(report, output_dir / "report.json")
    write_junit(report, output_dir / "junit.xml")
    if any(item.status == "error" for item in results):
        return 2
    return 1 if any(item.status == "fail" for item in results) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hwcheck",
        description="Collect Ubuntu hardware evidence and run compatibility checks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-checks", help="List registered checks.")
    list_parser.set_defaults(handler=lambda args: list_checks())

    inventory_parser = subparsers.add_parser("inventory", help="Collect host inventory.")
    inventory_parser.add_argument(
        "--output",
        type=Path,
        help="Write inventory JSON to this path; otherwise print it.",
    )
    inventory_parser.add_argument("--timeout", type=float, default=20.0)
    inventory_parser.set_defaults(handler=inventory_command)

    run_parser = subparsers.add_parser("run", help="Run a TOML test plan.")
    run_parser.add_argument("--plan", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, default=Path("results"))
    run_parser.add_argument("--timeout", type=float, default=20.0)
    run_parser.set_defaults(handler=run_command)
    return parser


def list_checks() -> int:
    for check_id, description in available_checks():
        print(f"{check_id:24} {description}")
    return 0


def inventory_command(args: argparse.Namespace) -> int:
    import json

    data = collect_inventory(CommandRunner(), timeout=args.timeout).to_dict()
    serialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


def run_command(args: argparse.Namespace) -> int:
    try:
        return run_plan(args.plan, args.output, args.timeout)
    except (OSError, ValueError) as exc:
        print(f"hwcheck: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
