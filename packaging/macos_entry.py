"""PyInstaller entry point for the macOS app bundle."""

from usb_vault.ui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
