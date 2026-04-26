"""Tiny build-time helper for build_installer.bat.

Reading the version and rewriting installer.iss in pure Python avoids the
quote-escaping nightmare of trying to do it inline in a Windows .bat
('cmd' has its own ideas about how single/double quotes interact with
'for /f' loops, which silently broke the previous version of this).

Commands:
    python _build_helper.py version
        -> prints APP_VERSION from main.py to stdout, exits 0
        -> prints error to stderr and exits 1 on failure

    python _build_helper.py update-iss <version>
        -> rewrites installer.iss AppVersion= and OutputBaseFilename= lines
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def get_version() -> str:
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("APP_VERSION not found in main.py")
    return match.group(1)


def update_installer(version: str) -> None:
    iss = ROOT / "installer.iss"
    text = iss.read_text(encoding="utf-8")
    text = re.sub(r"^AppVersion=.*$",
                  f"AppVersion={version}", text, flags=re.M)
    text = re.sub(r"^OutputBaseFilename=.*$",
                  f"OutputBaseFilename=MemoryNestSync_Setup_v{version}",
                  text, flags=re.M)
    iss.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: _build_helper.py {version|update-iss <version>}",
              file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "version":
            print(get_version())
            return 0
        if cmd == "update-iss":
            if len(argv) < 3:
                print("ERROR: update-iss requires a version argument",
                      file=sys.stderr)
                return 2
            update_installer(argv[2])
            print(f"installer.iss updated to v{argv[2]}")
            return 0
        print(f"ERROR: unknown command '{cmd}'", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
