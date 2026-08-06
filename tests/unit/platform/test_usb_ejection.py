"""Tests for session-scoped macOS USB-key ejection."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from usb_vault.platform.macos.usb_ejection import (
    MacOsSessionUsbEjector,
    volume_root_for_keyfile,
)


@dataclass
class FakeDiskutil:
    """Capture diskutil invocations without touching real mounted volumes."""

    return_codes: dict[str, int] = field(default_factory=dict)
    commands: list[tuple[str, ...]] = field(default_factory=list)

    def __call__(
        self,
        command: tuple[str, ...],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        assert timeout == 3.0
        self.commands.append(command)
        return subprocess.CompletedProcess(
            args=command,
            returncode=self.return_codes.get(command[-1], 0),
        )


def test_volume_root_requires_a_keyfile_beneath_a_mounted_volume() -> None:
    assert volume_root_for_keyfile(Path("/Volumes/Key/.authkey")) == Path("/Volumes/Key")
    assert volume_root_for_keyfile(Path("/Volumes/Key/nested/.authkey")) == Path("/Volumes/Key")
    assert volume_root_for_keyfile(Path("/tmp/.authkey")) is None
    assert volume_root_for_keyfile(Path("/Volumes/.authkey")) is None


def test_ejector_deduplicates_only_session_used_key_volumes() -> None:
    diskutil = FakeDiskutil()
    ejector = MacOsSessionUsbEjector(
        platform_name="darwin",
        command_runner=diskutil,
    )

    ejector.record_keyfile_paths(
        (
            Path("/Volumes/Personal/.authkey"),
            Path("/Volumes/Backup/.authkey"),
            Path("/Volumes/Personal/backup.authkey"),
            Path("/tmp/development.authkey"),
        )
    )

    results = ejector.eject_accessed_volumes()

    assert diskutil.commands == [
        ("/usr/sbin/diskutil", "eject", "/Volumes/Backup"),
        ("/usr/sbin/diskutil", "eject", "/Volumes/Personal"),
    ]
    assert [result.succeeded for result in results] == [True, True]
    assert ejector.accessed_volume_paths == ()


def test_one_failed_ejection_does_not_skip_another_volume() -> None:
    diskutil = FakeDiskutil(return_codes={"/Volumes/Backup": 1})
    ejector = MacOsSessionUsbEjector(
        platform_name="darwin",
        command_runner=diskutil,
    )
    ejector.record_keyfile_paths(
        (
            Path("/Volumes/Backup/.authkey"),
            Path("/Volumes/Personal/.authkey"),
        )
    )

    results = ejector.eject_accessed_volumes()

    assert [result.succeeded for result in results] == [False, True]
    assert len(diskutil.commands) == 2


def test_ejector_is_inactive_outside_macos() -> None:
    diskutil = FakeDiskutil()
    ejector = MacOsSessionUsbEjector(
        platform_name="linux",
        command_runner=diskutil,
    )
    ejector.record_keyfile_path(Path("/Volumes/Personal/.authkey"))

    assert ejector.eject_accessed_volumes() == ()
    assert diskutil.commands == []
