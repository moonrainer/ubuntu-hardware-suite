# Ubuntu Hardware Suite

`ubuntu-hardware-suite` is a small foundation for verifying that Ubuntu can
identify hardware, bind expected drivers, and expose usable system resources.
It is intended to grow into a certification-style provider with repeatable
plans, evidence, and machine-readable results.

## What is included

- A read-only inventory collector for OS, kernel, PCI, USB, block, and network
  information.
- NVIDIA GPU compatibility evidence from PCI driver binding and `nvidia-smi`,
  including model, driver version, PCI bus ID, memory, and temperature.
- A check registry with stable check IDs.
- A TOML test plan format.
- JSON output for automation and JUnit XML output for CI systems.
- Safe defaults that skip checks when the required Ubuntu utility is missing.
- Unit tests that mock command output, so development does not require Linux
  hardware.

The suite deliberately separates **compatibility evidence** from **stress or
destructive validation**. A future provider can add workload checks for GPUs,
storage, networking, USB, audio, suspend/resume, and firmware without changing
the reporting contract.

## Quick start on Ubuntu

```bash
sudo apt update
sudo apt install -y pciutils usbutils util-linux iproute2 python3-venv
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

hwcheck list-checks
hwcheck inventory --output inventory.json
hwcheck run --plan plans/base.toml --output results
```

The command writes `results/report.json` and `results/junit.xml`. The process
exits with status 0 when no check fails, 1 when a check fails, and 2 when a
check errors or the invocation is invalid.

## Plan format

Plans are intentionally small and declarative:

```toml
[plan]
name = "ubuntu-base"
description = "Read-only host and driver readiness checks"

checks = [
  "host.os",
  "host.kernel",
  "pci.driver_binding",
  "network.link",
  "storage.root",
]
```

Add a new check by implementing a function in
`src/ubuntu_hardware_suite/checks.py` and registering it in `CHECKS`.

The base plan includes `gpu.nvidia`. It skips on systems without NVIDIA
hardware, and on NVIDIA systems it expects the proprietary `nvidia` kernel
driver plus a working `nvidia-smi` query. An RTX 5080 is identified by the
reported model name; the check does not hard-code that model, so it also
covers other NVIDIA GPUs.

## Recommended roadmap

1. Keep the base profile read-only and collect stable evidence.
2. Add device-class providers: GPU, storage, network, USB, audio, Bluetooth,
   camera, and virtualization passthrough.
3. Add explicit environment gates for power, suspend/resume, reboot, and
   destructive I/O tests.
4. Add a hardware identity and driver-policy schema so expected devices can be
   supplied by a vendor.
5. Sign result bundles and upload them to a service that stores the exact
   Ubuntu release, kernel, firmware, plan revision, and raw evidence.
6. Add a lab runner for reboot-required tests and a quarantine mechanism for
   known flaky hardware or lab infrastructure.

## Safety and trust model

The initial checks invoke only information-gathering commands. Do not treat a
green base profile as proof of performance, stability under load, suspend
support, or long-term driver quality. Those properties need dedicated,
versioned tests with explicit resource and recovery requirements.
