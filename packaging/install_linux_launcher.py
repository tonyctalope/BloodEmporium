"""Install a launcher for this checkout in the current user's application menu."""
import os
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    applications = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    executable = str(root / "run-linux.sh")
    for char in ('\\', '"', '`', '$'):
        executable = executable.replace(char, '\\' + char)
    executable = executable.replace('%', '%%')
    entry = applications / "bloodemporium.desktop"
    entry.write_text(
        "[Desktop Entry]\nType=Application\nName=Blood Emporium\n"
        "Comment=Configure and automate the Dead by Daylight Bloodweb\n"
        f'Exec="{executable}"\nIcon={root / "assets/images/inspo1.png"}\n'
        "Terminal=false\nCategories=Game;Utility;\n")
    print(f"Installed {entry}")


if __name__ == "__main__":
    main()
