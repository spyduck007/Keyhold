"""Safely eject USB-key volumes used during one desktop-app session."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from usb_vault.platform.macos.usb_discovery import DEFAULT_VOLUMES_ROOT

DiskutilRunner = Callable[[tuple[str, ...], float], subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class UsbEjectionResult:
    """Outcome of an attempted session-volume ejection."""

    volume_path: Path
    succeeded: bool


def volume_root_for_keyfile(
    keyfile_path: Path,
    *,
    volumes_root: Path = DEFAULT_VOLUMES_ROOT,
) -> Path | None:
    """Return the mounted-volume root containing a keyfile, if it is under /Volumes."""
    resolved_keyfile_path = keyfile_path.resolve(strict=False)
    resolved_volumes_root = volumes_root.resolve(strict=False)

    try:
        relative_path = resolved_keyfile_path.relative_to(resolved_volumes_root)
    except ValueError:
        return None

    if len(relative_path.parts) < 2:
        return None

    return resolved_volumes_root / relative_path.parts[0]


@dataclass(slots=True)
class MacOsSessionUsbEjector:
    """Remember used USB-key volumes and eject them once the app closes."""

    volumes_root: Path = DEFAULT_VOLUMES_ROOT
    platform_name: str = sys.platform
    command_runner: DiskutilRunner | None = None
    _accessed_volume_paths: set[Path] = field(default_factory=set, init=False, repr=False)

    def record_keyfile_path(self, keyfile_path: Path) -> None:
        """Remember the mounted volume containing an accepted or used keyfile."""
        volume_path = volume_root_for_keyfile(
            keyfile_path,
            volumes_root=self.volumes_root,
        )

        if volume_path is not None:
            self._accessed_volume_paths.add(volume_path)

    def record_keyfile_paths(self, keyfile_paths: Iterable[Path]) -> None:
        """Remember each mounted volume that supplied an additional keyfile."""
        for keyfile_path in keyfile_paths:
            self.record_keyfile_path(keyfile_path)

    @property
    def accessed_volume_paths(self) -> tuple[Path, ...]:
        """Return the tracked volumes in deterministic order for diagnostics and tests."""
        return tuple(sorted(self._accessed_volume_paths, key=lambda path: str(path).casefold()))

    def eject_accessed_volumes(self) -> tuple[UsbEjectionResult, ...]:
        """Eject only session-used mounted USB-key volumes; never raise while closing."""
        if self.platform_name != "darwin":
            return ()

        volume_paths = self.accessed_volume_paths
        self._accessed_volume_paths.clear()
        results: list[UsbEjectionResult] = []

        for volume_path in volume_paths:
            try:
                completed = self._run_diskutil_eject(volume_path)
            except (
                OSError,
                subprocess.TimeoutExpired,
            ):
                results.append(UsbEjectionResult(volume_path=volume_path, succeeded=False))
                continue

            results.append(
                UsbEjectionResult(
                    volume_path=volume_path,
                    succeeded=(completed.returncode == 0),
                )
            )

        return tuple(results)

    def _run_diskutil_eject(self, volume_path: Path) -> subprocess.CompletedProcess[str]:
        command = (
            "/usr/sbin/diskutil",
            "eject",
            str(volume_path),
        )

        if self.command_runner is not None:
            return self.command_runner(command, 3.0)

        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
