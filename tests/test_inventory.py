from ubuntu_hardware_suite.inventory import collect_cpu_cache, collect_cpu_clocksource, collect_cpu_numa, collect_cpu_topology, collect_edac_counters, collect_thermal_throttle_counts, parse_cpuinfo, parse_meminfo, collect_cpu_frequencies, collect_cpu_idle_states, parse_lscpu_json, parse_lspci, parse_nvidia_smi, parse_os_release


def test_parse_os_release():
    result = parse_os_release('ID=ubuntu\nVERSION_ID="24.04"\nNAME="Ubuntu"\n')
    assert result["ID"] == "ubuntu"
    assert result["VERSION_ID"] == "24.04"


def test_parse_lspci_driver_sections():
    text = (
        "00:02.0 VGA compatible controller: Example GPU\n"
        "\tSubsystem: Example\n"
        "\tKernel driver in use: i915\n"
        "\tKernel modules: i915\n"
        "03:00.0 Ethernet controller: Example NIC\n"
        "\tKernel driver in use: ixgbe\n"
    )
    devices = parse_lspci(text)
    assert devices[0]["address"] == "00:02.0"
    assert devices[0]["driver"] == "i915"
    assert devices[1]["driver"] == "ixgbe"


def test_parse_nvidia_smi_csv():
    output = (
        "NVIDIA GeForce RTX 5080, 570.86.16, 00000000:01:00.0, 16376, 42\n"
        "NVIDIA H100 PCIe, 570.86.16, 00000000:81:00.0, 81559, 39\n"
    )
    gpus = parse_nvidia_smi(output)
    assert gpus == [
        {
            "name": "NVIDIA GeForce RTX 5080",
            "driver_version": "570.86.16",
            "pci_bus_id": "00000000:01:00.0",
            "memory_total_mib": "16376",
            "temperature_gpu_c": "42",
        },
        {
            "name": "NVIDIA H100 PCIe",
            "driver_version": "570.86.16",
            "pci_bus_id": "00000000:81:00.0",
            "memory_total_mib": "81559",
            "temperature_gpu_c": "39",
        }
    ]


def test_parse_lscpu_json():
    text = '{"lscpu":[{"field":"CPU(s):","data":"16"},{"field":"Model name:","data":"Example CPU"}]}'
    assert parse_lscpu_json(text) == {"CPU(s)": "16", "Model name": "Example CPU"}


def test_collect_cpu_frequencies_from_sysfs_fixture(tmp_path):
    cpufreq = tmp_path / "cpu0" / "cpufreq"
    cpufreq.mkdir(parents=True)
    (cpufreq / "scaling_driver").write_text("intel_pstate\n", encoding="utf-8")
    (cpufreq / "scaling_governor").write_text("powersave\n", encoding="utf-8")
    (cpufreq / "scaling_cur_freq").write_text("2400000\n", encoding="utf-8")
    assert collect_cpu_frequencies(tmp_path) == [
        {
            "cpu": "cpu0",
            "scaling_driver": "intel_pstate",
            "scaling_governor": "powersave",
            "scaling_cur_freq": "2400000",
        }
    ]


def test_collect_cpu_idle_states_from_sysfs_fixture(tmp_path):
    state = tmp_path / "cpu0" / "cpuidle" / "state1"
    state.mkdir(parents=True)
    (state / "name").write_text("C1\n", encoding="utf-8")
    (state / "disable").write_text("0\n", encoding="utf-8")
    assert collect_cpu_idle_states(tmp_path) == [
        {"cpu": "cpu0", "state": "state1", "name": "C1", "disable": "0"}
    ]

def test_parse_meminfo_and_cpuinfo():
    mem = parse_meminfo("MemTotal:       16384 kB\nMemFree:          1024 kB\n")
    cpu = parse_cpuinfo(
        "vendor_id\t: GenuineIntel\nmodel name\t: Example CPU\nmicrocode\t: 0x1\nflags\t: fpu tsc\n"
    )
    assert mem["MemTotal"] == 16384
    assert cpu["vendor_id"] == "GenuineIntel"
    assert cpu["microcodes"] == ["0x1"]
    assert "tsc" in cpu["flags"]


def test_collect_additional_cpu_sysfs_evidence(tmp_path):
    topology = tmp_path / "cpu0" / "topology"
    topology.mkdir(parents=True)
    (topology / "physical_package_id").write_text("0\n", encoding="utf-8")
    (topology / "core_id").write_text("0\n", encoding="utf-8")
    cache = tmp_path / "cpu0" / "cache" / "index0"
    cache.mkdir(parents=True)
    (cache / "level").write_text("1\n", encoding="utf-8")
    (cache / "type").write_text("Data\n", encoding="utf-8")
    (cache / "size").write_text("32K\n", encoding="utf-8")
    assert collect_cpu_topology(tmp_path)[0]["physical_package_id"] == "0"
    assert collect_cpu_cache(tmp_path)[0]["type"] == "Data"


def test_collect_numa_clocksource_edac_and_throttle_fixtures(tmp_path):
    node = tmp_path / "node"
    (node / "node0").mkdir(parents=True)
    (node / "online").write_text("0\n", encoding="utf-8")
    (node / "node0" / "cpulist").write_text("0-3\n", encoding="utf-8")
    clock = tmp_path / "clock"
    clock.mkdir()
    (clock / "current_clocksource").write_text("tsc\n", encoding="utf-8")
    edac = tmp_path / "edac" / "mc0"
    edac.mkdir(parents=True)
    (edac / "ce_count").write_text("1\n", encoding="utf-8")
    thermal = tmp_path / "cpu0" / "thermal_throttle"
    thermal.mkdir(parents=True)
    (thermal / "core_throttle_count").write_text("0\n", encoding="utf-8")
    assert collect_cpu_numa(node)["online"] == "0"
    assert collect_cpu_clocksource(clock)["current"] == "tsc"
    assert collect_edac_counters(tmp_path / "edac")[0]["ce_count"] == "1"
    assert collect_thermal_throttle_counts(tmp_path)[0]["core_throttle_count"] == "0"