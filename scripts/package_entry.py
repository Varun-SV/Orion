"""Standalone desktop entry point, kept separate from the legacy Qt launcher."""
from orion.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
