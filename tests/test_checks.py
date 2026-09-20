from ubuntu_hardware_suite.checks import (
    check_cpu_cache,
    check_cpu_clocksource,
    check_cpu_cstate_residency,
    check_cpu_edac,
    check_cpu_identity,
    check_cpu_microcode,
    check_cpu_numa,
    check_cpu_ram_per_core,
    check_cpu_throttle_history,
    check_cpu_vulnerabilities,
    check_cpu_cstates,
    check_cpu_frequency,
    check_cpu_stress,
    check_cpu_topology,
    check_nvidia_gpu,
    check_network_link,
    check_pci_driver_binding,
    check_storage_root,
)
from ubuntu_hardware_suite.models import CommandResult, HardwareInventory


def inventory(**overrides):
    commands = {
        "os_release": CommandResult(["cat"], 0),
        "cpu": CommandResult(["lscpu"], 0),
        "pci": CommandResult(["lspci"], 0),
        "usb": CommandResult(["lsusb"], 0),
        "block": CommandResult(["lsblk"], 0),
        "links": CommandResult(["ip"], 0),
        "nvidia_smi": CommandResult(["nvidia-smi"], 0),
    }
    values = {
        "collected_at": "2026-09-01T00:00:00+00:00",
        "platform": {"system": "Linux", "release": "6.8.0-test"},
        "os_release": {"ID": "ubuntu", "VERSION_ID": "24.04"},
        "commands": commands,
        "pci_devices": [],
        "usb_devices": [],
        "block_devices": {},
        "network_links": [],
        "nvidia_gpus": [],
        "cpu_info": {},
        "cpu_frequencies": [],
        "cpu_idle_states": [],
        "cpu_identity": {},
        "mem_info": {},
        "cpu_microcodes": [],
        "cpu_vulnerabilities": {},
        "cpu_topology": [],
        "cpu_cache": [],
        "cpu_numa": {},
        "cpu_clocksource": {},
        "edac_counters": [],
        "thermal_throttle_counts": [],    }
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


def test_nvidia_gpu_passes_for_supported_nvidia_models():
    models = [
        ("NVIDIA Corporation GB203 [GeForce RTX 5080]", "NVIDIA GeForce RTX 5080"),
        ("NVIDIA Corporation AD102GL [RTX 6000 Ada Generation]", "NVIDIA RTX 6000 Ada Generation"),
        ("NVIDIA Corporation GH100 [H100 PCIe]", "NVIDIA H100 PCIe"),
        ("NVIDIA Corporation AD104GL [L40S]", "NVIDIA L40S"),
    ]
    for pci_name, smi_name in models:
        result = check_nvidia_gpu(
            inventory(
                pci_devices=[
                    {
                        "address": "01:00.0",
                        "name": pci_name,
                        "driver": "nvidia",
                        "modules": ["nvidia"],
                    }
                ],
                nvidia_gpus=[
                    {
                        "name": smi_name,
                        "driver_version": "570.86.16",
                        "pci_bus_id": "00000000:01:00.0",
                        "memory_total_mib": "16376",
                        "temperature_gpu_c": "42",
                    }
                ],
            )
        )
        assert result.status == "pass"
        assert smi_name in result.summary


def test_nvidia_gpu_fails_when_bound_to_nouveau():
    result = check_nvidia_gpu(
        inventory(
            pci_devices=[
                {
                    "address": "01:00.0",
                    "name": "NVIDIA Corporation GPU",
                    "driver": "nouveau",
                    "modules": ["nouveau"],
                }
            ]
        )
    )
    assert result.status == "fail"

def test_cpu_topology_passes_with_lscpu_data():
    result = check_cpu_topology(
        inventory(cpu_info={"CPU(s)": "16", "Model name": "Example CPU"})
    )
    assert result.status == "pass"
    assert "16 CPU(s)" in result.summary


def test_cpu_frequency_passes_with_current_frequency():
    result = check_cpu_frequency(
        inventory(
            cpu_frequencies=[
                {
                    "cpu": "cpu0",
                    "scaling_driver": "intel_pstate",
                    "scaling_governor": "powersave",
                    "scaling_cur_freq": "2400000",
                    "scaling_min_freq": "800000",
                    "scaling_max_freq": "5000000",
                }
            ]
        )
    )
    assert result.status == "pass"
    assert "powersave" in result.summary


def test_cpu_cstates_require_at_least_one_enabled_state():
    disabled = check_cpu_cstates(
        inventory(
            cpu_idle_states=[
                {"cpu": "cpu0", "state": "state1", "name": "C1", "disable": "1"}
            ]
        )
    )
    enabled = check_cpu_cstates(
        inventory(
            cpu_idle_states=[
                {"cpu": "cpu0", "state": "state1", "name": "C1", "disable": "0"}
            ]
        )
    )
    assert disabled.status == "fail"
    assert enabled.status == "pass"


def test_cpu_stress_reports_stress_ng_result():
    passed = check_cpu_stress(
        inventory(commands={"cpu_stress": CommandResult(["stress-ng"], 0, stdout="ok")})
    )
    failed = check_cpu_stress(
        inventory(commands={"cpu_stress": CommandResult(["stress-ng"], 1, stderr="fail")})
    )
    assert passed.status == "pass"
    assert failed.status == "fail"

def test_cpu_identity_passes_with_cpuinfo_data():
    result = check_cpu_identity(
        inventory(cpu_identity={"vendor_id": "GenuineIntel", "model_name": "Example CPU"})
    )
    assert result.status == "pass"
    assert "GenuineIntel" in result.summary


def test_cpu_ram_per_core_enforces_threshold():
    passed = check_cpu_ram_per_core(
        inventory(mem_info={"MemTotal": 32 * 1048576}, cpu_info={"CPU(s)": "16"})
    )
    failed = check_cpu_ram_per_core(
        inventory(mem_info={"MemTotal": 4 * 1048576}, cpu_info={"CPU(s)": "8"})
    )
    assert passed.status == "pass"
    assert failed.status == "fail"


def test_cpu_microcode_fails_on_mixed_revisions():
    result = check_cpu_microcode(inventory(cpu_microcodes=["0x1", "0x2"]))
    assert result.status == "fail"


def test_cpu_vulnerabilities_fail_when_exposed():
    result = check_cpu_vulnerabilities(
        inventory(cpu_vulnerabilities={"spectre_v2": "Vulnerable"})
    )
    assert result.status == "fail"


def test_cpu_cache_numa_clocksource_pass_with_sysfs_data():
    cache = check_cpu_cache(
        inventory(cpu_cache=[{"level": "1", "type": "Data", "size": "32K"}])
    )
    numa = check_cpu_numa(inventory(cpu_numa={"online": "0", "nodes": []}))
    clock = check_cpu_clocksource(
        inventory(cpu_clocksource={"current": "tsc", "available": "tsc hpet"})
    )
    assert cache.status == "pass"
    assert numa.status == "pass"
    assert clock.status == "pass"


def test_cpu_cstate_residency_requires_usage_activity():
    result = check_cpu_cstate_residency(
        inventory(cpu_idle_states=[{"name": "C1", "disable": "0", "usage": "10"}])
    )
    assert result.status == "pass"


def test_cpu_ras_counters_report_failures():
    edac = check_cpu_edac(inventory(edac_counters=[{"ce_count": "0", "ue_count": "1"}]))
    throttle = check_cpu_throttle_history(
        inventory(thermal_throttle_counts=[{"core_throttle_count": "1", "package_throttle_count": "0"}])
    )
    assert edac.status == "fail"
    assert throttle.status == "fail"