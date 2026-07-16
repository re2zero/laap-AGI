#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SRC = Path(__file__).resolve().parent / "plugin" / "laap-source-plugin.ts"
OPENCODE_PLUGINS_DIR = Path.home() / ".config" / "opencode" / "plugins"
CONFIG_PATH = Path.home() / ".config" / "opencode" / "laap.jsonc"
CONFIG_EXAMPLE = Path(__file__).resolve().parent / "config.example.jsonc"

DEFAULT_PYTHON = shutil.which("python3") or "python3"


def detect_laap_root():
    env_root = os.environ.get("LAAP_ROOT", "")
    if env_root and Path(env_root).exists():
        return env_root
    return str(REPO_ROOT)


def check_bridge(laap_root, python_path):
    result = subprocess.run(
        [python_path, "-m", "opencode_integration.bridge", "--check"],
        cwd=laap_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"[ERROR] Bridge check failed:\n{result.stderr}")
        return False
    print(f"[OK] Bridge check passed:\n{result.stdout.strip()}")
    return True


def install_plugin():
    OPENCODE_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    dest = OPENCODE_PLUGINS_DIR / "laap-source-plugin.ts"
    shutil.copy2(PLUGIN_SRC, dest)
    print(f"[OK] Plugin installed: {dest}")


def install_config(laap_root):
    if CONFIG_PATH.exists():
        print(f"[SKIP] Config already exists: {CONFIG_PATH}")
        print("       Edit manually if you need to add 'bridge' section.")
        return

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_EXAMPLE, CONFIG_PATH)

    content = CONFIG_PATH.read_text()
    content = content.replace('"laap_root": ""', f'"laap_root": "{laap_root}"')
    CONFIG_PATH.write_text(content)
    print(f"[OK] Config installed: {CONFIG_PATH}")


def main():
    print("=== LAAP OpenCode Source Plugin Installer ===\n")

    python_path = DEFAULT_PYTHON
    laap_root = detect_laap_root()

    print(f"Python: {python_path}")
    print(f"LAAP_ROOT: {laap_root}")
    print()

    print("[1/3] Checking bridge...")
    bridge_ok = False
    try:
        bridge_ok = check_bridge(Path(__file__).resolve().parent, python_path)
    except Exception as e:
        print(f"[WARN] Bridge check error: {e}")
        print("       The bridge may still work at runtime.")
    print()

    print("[2/3] Installing plugin...")
    install_plugin()
    print()

    print("[3/3] Installing config...")
    install_config(laap_root)
    print()

    print("=== Installation Complete ===")
    print("Restart OpenCode to activate the LAAP source plugin.")
    if not bridge_ok:
        print("\n[NOTE] Bridge check failed. Verify Python environment and LAAP_ROOT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
