from ubuntu_hardware_suite.inventory import collect_cpu_frequencies, collect_cpu_idle_states, parse_lscpu_json, parse_lspci, parse_nvidia_smi, parse_os_release


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