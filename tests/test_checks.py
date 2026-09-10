from ubuntu_hardware_suite.checks import (
    check_network_link,
    check_pci_driver_binding,
    check_storage_root,
)
from ubuntu_hardware_suite.models import CommandResult, HardwareInventory


def inventory(**overrides):
    commands = {
        "os_release": CommandResult(["cat"], 0),
        "pci": CommandResult(["lspci"], 0),
        "usb": CommandResult(["lsusb"], 0),
        "block": CommandResult(["lsblk"], 0),
        "links": CommandResult(["ip"], 0),
    }
    values = {
        "collected_at": "2026-09-01T00:00:00+00:00",
        "platform": {"release": "6.8.0-test"},
        "os_release": {"ID": "ubuntu", "VERSION_ID": "24.04"},
        "commands": commands,
        "pci_devices": [],
        "usb_devices": [],
        "block_devices": {},
        "network_links": [],
    }
    values.update(overrides)
    return HardwareInventory(**values)


def test_pci_binding_fails_for_unbound_device():
    result = check_pci_driver_binding(
        inventory(
            pci_devices=[
                {
                    "address": "04:00.0",
                    "name": "Example NIC",
                    "driver": None,
                    "modules": ["example"],
                }
            ]
        )
    )
    assert result.status == "fail"


def test_network_link_passes_for_up_interface():
    result = check_network_link(
        inventory(network_links=[{"ifname": "enp1s0", "operstate": "UP"}])
    )
    assert result.status == "pass"


def test_storage_root_requires_root_mount():
    result = check_storage_root(
        inventory(block_devices={"blockdevices": [{"name": "nvme0n1", "mountpoints": [None]}]})
    )
    assert result.status == "fail"
