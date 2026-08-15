# Keyhold

A password-and-USB protected encrypted vault, with a desktop app and a CLI.

## Building the macOS app

To produce a double-clickable `Keyhold.app`:

```bash
pip install -e ".[packaging]"
./scripts/build_macos_app.sh
```

The bundle is written to `dist/Keyhold.app`. It's built with
[PyInstaller](https://pyinstaller.org/) and carries the icon in
`packaging/icon/AppIcon.icns`. To change the icon, edit
`packaging/icon/generate_icon.py`, run it to regenerate `AppIcon.png`, then
run `packaging/icon/build_icns.sh` to rebuild the `.icns` before rebuilding
the app.

`dist/` and `build/` are build output and are not committed.

### Opening a `.vault` file from Finder

The bundle declares `.vault` as its own document type
(`packaging/Keyhold.spec`), so once `Keyhold.app` is in `/Applications`,
double-clicking any `.vault` file launches (or focuses) Keyhold with that
vault's path already filled in — just enter the password and connect the
USB key. The build script also registers the freshly built bundle with
Launch Services, so this works immediately after a build, before macOS
would otherwise notice the new app.
