#!/usr/bin/env python3
"""Preflight check: pdflatex, poppler's pdfinfo/pdftotext, and the Python version.

Prints the install command for the detected OS when something is missing; installs
need sudo, so this only prescribes and the user runs the command.

usage : env_check.py
exit  : 0 everything present / 4 something missing (degraded mode, not a hard stop:
        the pipeline runs but skips the compile and page-fit checks)
"""
import platform
import shutil
import sys
from pathlib import Path

INSTALL = {
    "latex": {
        "debian": "sudo apt install texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended",
        "arch": "sudo pacman -S texlive-latexextra texlive-fontsrecommended",
        "fedora": "sudo dnf install texlive-scheme-medium",
        "macos": "brew install --cask mactex",
        "windows": "winget install MiKTeX.MiKTeX",
    },
    "poppler": {
        "debian": "sudo apt install poppler-utils",
        "arch": "sudo pacman -S poppler",
        "fedora": "sudo dnf install poppler-utils",
        "macos": "brew install poppler",
        "windows": "scoop install poppler",
    },
}
FALLBACK = {
    "latex": "install a TeX Live scheme providing pdflatex plus the packages in README.md",
    "poppler": "install poppler (sometimes packaged as poppler-utils)",
}

TOOLS = [("pdflatex", "latex"), ("pdfinfo", "poppler"), ("pdftotext", "poppler")]


def detect_os():
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in ("win32", "cygwin"):
        return "windows"
    ids = []
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith(("ID=", "ID_LIKE=")):
                ids += line.split("=", 1)[1].strip().strip('"').lower().split()
    except OSError:
        pass
    aliases = {"ubuntu": "debian", "rhel": "fedora", "centos": "fedora"}
    for i in ids:
        key = aliases.get(i, i)
        if key in INSTALL["latex"]:
            return key
    return "linux"  # unknown distro; fall back to generic advice


def main():
    os_key = detect_os()
    print(f"platform : {os_key}")

    missing = []  # groups, in first-seen order
    py = platform.python_version()
    if sys.version_info >= (3, 10):
        print(f"python   : OK ({py})")
    else:
        print(f"python   : TOO OLD ({py}; need 3.10+)")
        missing.append("python")

    for tool, group in TOOLS:
        path = shutil.which(tool)
        if path:
            print(f"{tool:<9}: OK ({path})")
        else:
            print(f"{tool:<9}: MISSING")
            if group not in missing:
                missing.append(group)

    if not missing:
        print("\nenv_check: everything present.")
        return 0

    print("\nTo install:")
    for group in missing:
        if group == "python":
            print("  Python 3.10+ from your OS package manager or python.org")
        else:
            print(f"  {INSTALL[group].get(os_key) or FALLBACK[group]}")
    return 4


if __name__ == "__main__":
    sys.exit(main())
