"""Atlas Studio V3 entry point."""

from app.atlas_application import AtlasApplication
from app.main_window import MainWindow


def main() -> int:
    app = AtlasApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
