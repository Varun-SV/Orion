"""
Orion — Media Library Organizer
Entry point: initialise app, open DB, show wizard or main window.
"""
from __future__ import annotations
import os, sys

# xkbcommon looks up the compose file using LC_CTYPE.  Legacy encodings like
# ISO-8859-1 have no compose file on most Linux systems, producing spurious
# "No Compose file for locale" errors.  Switching to UTF-8 before QApplication
# starts silences the noise without affecting any other locale behaviour.
_lc = os.environ.get("LC_CTYPE") or os.environ.get("LANG", "")
if _lc and "." in _lc and not _lc.upper().endswith("UTF-8"):
    os.environ["LC_CTYPE"] = _lc.split(".")[0] + ".UTF-8"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from core.config import Config
from core.database import Database
from ui.styles import DARK_STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Orion")
    app.setOrganizationName("Orion")
    app.setQuitOnLastWindowClosed(False)   # stay alive in system tray
    app.setStyleSheet(DARK_STYLESHEET)

    config = Config()
    db     = Database(config.db_path)
    db.open()

    first_launch = config.is_first_launch()

    if first_launch:
        from ui.wizard import SetupWizard
        wizard = SetupWizard(db, config)
        if wizard.exec() != wizard.DialogCode.Accepted:
            db.close()
            sys.exit(0)
        config.mark_launched()

    from ui.main_window import MainWindow
    window = MainWindow(db, config)
    window.show()

    code = app.exec()
    db.close()
    sys.exit(code)


if __name__ == "__main__":
    main()
