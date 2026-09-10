from ubuntu_hardware_suite.inventory import parse_lspci, parse_os_release


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
