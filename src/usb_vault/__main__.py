"""Allow ``python -m usb_vault`` to run the CLI."""

from usb_vault.cli.main import main

raise SystemExit(main())
