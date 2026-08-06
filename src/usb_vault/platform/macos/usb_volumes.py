"""Discover mounted external USB volumes available for new vault keys."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from usb_vault.platform.macos.usb_discovery import DEFAULT_VOLUMES_ROOT

DiskutilInfoRunner = Callable[[tuple[str, ...], float], subprocess.CompletedProcess[str]]


class UsbVolumeLocator(Protocol):
    """Locate mounted external USB volumes eligible for a vault key."""

    def external_usb_volumes(self) -> tuple[Path, ...]:
        """Return mounted external USB volume roots in display order."""


@dataclass(frozen=True, slots=True)
class MacOsUsbVolumeLocator:
    """List mounted macOS volumes reported by ``diskutil`` as USB devices."""

    volumes_root: Path = DEFAULT_VOLUMES_ROOT
    platform_name: str = sys.platform
    command_runner: DiskutilInfoRunner | None = None

    def external_usb_volumes(self) -> tuple[Path, ...]:
        """Return deterministic external USB-volume roots.

        Inspecting each mount through ``diskutil`` prevents disk images, network
        shares, and internal volumes from being offered as hardware-key targets.
        """
        if self.platform_name != "darwin":
            return ()

        return tuple(
            volume_path
            for volume_path in self._mounted_volume_paths()
            if self._is_usb_volume(volume_path)
        )

    def _mounted_volume_paths(self) -> tuple[Path, ...]:
        try:
            with os.scandir(self.volumes_root) as entries:
                volume_paths: list[Path] = []

                for entry in entries:
                    try:
                        is_directory = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        continue

                    if is_directory:
                        volume_paths.append(Path(entry.path))
        except OSError:
            return ()

        return tuple(
            sorted(
                volume_paths,
                key=lambda path: (
                    path.name.casefold(),
                    str(path),
                ),
            )
        )

    def _is_usb_volume(self, volume_path: Path) -> bool:
        command = (
            "/usr/sbin/diskutil",
            "info",
            "-plist",
            str(volume_path),
        )

        try:
            if self.command_runner is not None:
                result = self.command_runner(command, 3.0)
            else:
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return False

        if result.returncode != 0:
            return False

        try:
            properties = plistlib.loads(result.stdout.encode())
        except (
            AttributeError,
            plistlib.InvalidFileException,
            ValueError,
        ):
            return False

        bus_protocol = properties.get("BusProtocol", properties.get("Protocol"))
        is_internal = properties.get("Internal")
        is_writable = properties.get("WritableVolume")

        return (
            isinstance(bus_protocol, str)
            and bus_protocol.casefold() == "usb"
            and is_internal is not True
            and is_writable is not False
        )
