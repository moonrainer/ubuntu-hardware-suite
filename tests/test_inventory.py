from ubuntu_hardware_suite.inventory import parse_lspci, parse_nvidia_smi, parse_os_release


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
