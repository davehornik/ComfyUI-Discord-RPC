"""Dependency installer for ComfyUI Discord Rich Presence.

ComfyUI-Manager runs this script automatically when the extension is
installed. You can also run it by hand to install the dependencies into
the ComfyUI virtual environment:

    python install.py

It installs everything listed in requirements.txt (currently: pypresence)
into the interpreter that runs it, so make sure to use ComfyUI's Python.
"""

import os
import subprocess
import sys


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    requirements = os.path.join(here, "requirements.txt")

    print("[Discord RPC] Installing dependencies from requirements.txt ...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", requirements]
    )
    print("[Discord RPC] Dependencies installed successfully.")


if __name__ == "__main__":
    main()
