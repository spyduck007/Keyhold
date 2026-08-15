# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Keyhold.app.

Kept as a maintained .spec (rather than plain CLI flags) so the bundle can
declare '.vault' as its own document type — this is what lets Finder open
Keyhold when you double-click a .vault file. See scripts/build_macos_app.sh.
"""

from pathlib import Path

REPO_ROOT = Path(SPECPATH).parent  # noqa: F821 - injected by PyInstaller
ICON_PATH = str(REPO_ROOT / "packaging" / "icon" / "AppIcon.icns")

VAULT_UTI = "com.keyhold.vault"

a = Analysis(  # noqa: F821 - injected by PyInstaller
    [str(REPO_ROOT / "packaging" / "macos_entry.py")],
    pathex=[str(REPO_ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821 - injected by PyInstaller

exe = EXE(  # noqa: F821 - injected by PyInstaller
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Keyhold",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=ICON_PATH,
)

coll = COLLECT(  # noqa: F821 - injected by PyInstaller
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="Keyhold",
)

app = BUNDLE(  # noqa: F821 - injected by PyInstaller
    coll,
    name="Keyhold.app",
    icon=ICON_PATH,
    bundle_identifier="com.keyhold.desktop",
    info_plist={
        "CFBundleName": "Keyhold",
        "CFBundleDisplayName": "Keyhold",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.utilities",
        # Declare '.vault' as a document type this app owns, so Finder
        # offers (and defaults to) Keyhold for double-clicking one.
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Keyhold Vault",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
                "LSItemContentTypes": [VAULT_UTI],
                "CFBundleTypeIconFile": "AppIcon.icns",
            }
        ],
        "UTExportedTypeDeclarations": [
            {
                "UTTypeIdentifier": VAULT_UTI,
                "UTTypeDescription": "Keyhold Encrypted Vault",
                "UTTypeConformsTo": ["public.data"],
                "UTTypeTagSpecification": {
                    "public.filename-extension": ["vault"],
                },
                "UTTypeIconFile": "AppIcon.icns",
            }
        ],
    },
)
