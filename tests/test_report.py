import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ubuntu_hardware_suite.models import CheckResult, CommandResult, HardwareInventory, SuiteReport
from ubuntu_hardware_suite.report import write_json, write_junit


def make_report():
    host = HardwareInventory(
        collected_at="2026-09-01T00:00:00+00:00",
        platform={"system": "Linux"},
        os_release={"ID": "ubuntu"},
        commands={"pci": CommandResult(["lspci"], 0)},
    )
    return SuiteReport(
        schema_version="1.0",
        suite="ubuntu-hardware-suite",
        plan={"name": "test"},
        started_at=host.collected_at,
        finished_at=host.collected_at,
        host=host,
        results=[
            CheckResult("host.os", "OS", "pass", "ok"),
            CheckResult("network.link", "Network", "skip", "missing"),
        ],
    )


def test_report_writers(tmp_path: Path):
    report = make_report()
    json_path = tmp_path / "report.json"
    xml_path = tmp_path / "junit.xml"
    write_json(report, json_path)
    write_junit(report, xml_path)
    assert json.loads(json_path.read_text())["summary"]["skip"] == 1
    root = ET.parse(xml_path).getroot()
    assert root.attrib["tests"] == "2"
    assert root.attrib["skipped"] == "1"
