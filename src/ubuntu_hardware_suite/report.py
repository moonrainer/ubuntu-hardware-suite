from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import SuiteReport


def write_json(report: SuiteReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_junit(report: SuiteReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suite = ET.Element(
        "testsuite",
        {
            "name": report.suite,
            "tests": str(len(report.results)),
            "failures": str(sum(item.status == "fail" for item in report.results)),
            "errors": str(sum(item.status == "error" for item in report.results)),
            "skipped": str(sum(item.status == "skip" for item in report.results)),
            "time": f"{sum(item.duration_s for item in report.results):.3f}",
        },
    )
    for result in report.results:
        case = ET.SubElement(
            suite,
            "testcase",
            {"name": result.check_id, "time": f"{result.duration_s:.3f}"},
        )
        if result.status == "skip":
            ET.SubElement(case, "skipped", {"message": result.summary})
        elif result.status == "fail":
            failure = ET.SubElement(case, "failure", {"message": result.summary})
            failure.text = result.details
        elif result.status == "error":
            error = ET.SubElement(case, "error", {"message": result.summary})
            error.text = result.details
        output = ET.SubElement(case, "system-out")
        output.text = result.summary + (f"\n{result.details}" if result.details else "")
    ET.indent(suite, space="  ")
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)
