"""Tests for external USB-volume discovery used by new-vault setup."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from usb_vault.platform.macos.usb_volumes import MacOsUsbVolumeLocator


class FakeDiskutil:
    """Return deterministic ``diskutil info -plist`` responses."""

    def __init__(
        self,
        bus_protocols: dict[Path, str],
    ) -> None:
        self.bus_protocols = bus_protocols
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self,
        command: tuple[str, ...],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        self.calls.append(command)
        volume_path = Path(command[-1])
        bus_protocol = self.bus_protocols.get(volume_path)

        if bus_protocol is None:
            return subprocess.CompletedProcess(command, 1, "", "not found")

        return subprocess.CompletedProcess(
            command,
            0,
            plistlib.dumps({"BusProtocol": bus_protocol}).decode(),
            "",
        )


def test_locator_returns_only_usb_volume_roots_in_display_order(
    tmp_path: Path,
) -> None:
    volumes_root = tmp_path / "Volumes"
    alpha = volumes_root / "Alpha"
    disk_image = volumes_root / "Disk Image"
    bravo = volumes_root / "bravo"

    for volume_path in (alpha, disk_image, bravo):
        volume_path.mkdir(parents=True)

    diskutil = FakeDiskutil(
        {
            alpha: "USB",
            disk_image: "Disk Image",
            bravo: "usb",
        }
    )
    locator = MacOsUsbVolumeLocator(
        volumes_root=volumes_root,
        platform_name="darwin",
        command_runner=diskutil,
    )

    assert locator.external_usb_volumes() == (alpha, bravo)
    assert diskutil.calls == [
        ("/usr/sbin/diskutil", "info", "-plist", str(alpha)),
        ("/usr/sbin/diskutil", "info", "-plist", str(bravo)),
        ("/usr/sbin/diskutil", "info", "-plist", str(disk_image)),
    ]


def test_locator_does_not_call_diskutil_off_macos(
    tmp_path: Path,
) -> None:
    volume_path = tmp_path / "Volumes" / "USB"
    volume_path.mkdir(parents=True)
    diskutil = FakeDiskutil({volume_path: "USB"})
    locator = MacOsUsbVolumeLocator(
        volumes_root=volume_path.parent,
        platform_name="linux",
        command_runner=diskutil,
    )

    assert locator.external_usb_volumes() == ()
    assert diskutil.calls == []
