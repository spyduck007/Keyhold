# USB Vault

A password-and-USB protected encrypted vault, with a desktop app and a CLI.

## Building the macOS app

To produce a double-clickable `USB Vault.app`:

```bash
pip install -e ".[packaging]"
./scripts/build_macos_app.sh
```

The bundle is written to `dist/USB Vault.app`. It's built with
[PyInstaller](https://pyinstaller.org/) and carries the icon in
`packaging/icon/AppIcon.icns`. To change the icon, edit
`packaging/icon/generate_icon.py`, run it to regenerate `AppIcon.png`, then
run `packaging/icon/build_icns.sh` to rebuild the `.icns` before rebuilding
the app.

`dist/` and `build/` are build output and are not committed.
