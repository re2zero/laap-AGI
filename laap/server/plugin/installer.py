"""LAAP OpenCode Plugin Installer.

Copies the LAAP plugin to OpenCode's plugins directory and creates default config.
"""

import shutil
from pathlib import Path


def get_plugin_path() -> Path:
    """Get the path to the bundled laap-plugin.js file."""
    return Path(__file__).parent / "laap-plugin.js"


def get_opencode_plugins_dir() -> Path:
    """Get the path to OpenCode's plugins directory."""
    return Path.home() / ".config" / "opencode" / "plugins"


def get_config_path() -> Path:
    """Get the path to the LAAP config file."""
    return Path.home() / ".config" / "opencode" / "laap.jsonc"


def get_default_config_path() -> Path:
    """Get the path to the default LAAP config template."""
    # installer.py lives at <root>/laap/server/plugin/installer.py → 4 parents
    # up reaches the repo root, where laap_brain/ default_config.jsonc lives.
    return Path(__file__).parent.parent.parent.parent / "laap_brain" / "default_config.jsonc"


def install_plugin(force: bool = False) -> bool:
    """Install the LAAP plugin to OpenCode's plugins directory.
    
    Args:
        force: If True, overwrite existing plugin.
        
    Returns:
        True if installed successfully, False if already exists and force=False.
    """
    plugin_src = get_plugin_path()
    plugins_dir = get_opencode_plugins_dir()
    plugin_dst = plugins_dir / "laap-plugin.js"
    
    if not plugin_src.exists():
        raise FileNotFoundError(f"Plugin file not found: {plugin_src}")
    
    if plugin_dst.exists() and not force:
        print(f"Plugin already exists at {plugin_dst}")
        return False
    
    plugins_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plugin_src, plugin_dst)
    print(f"Installed plugin to {plugin_dst}")
    return True


def install_config(force: bool = False) -> bool:
    """Install the default LAAP config if it doesn't exist.
    
    Args:
        force: If True, overwrite existing config.
        
    Returns:
        True if installed successfully, False if already exists and force=False.
    """
    config_dst = get_config_path()
    config_src = get_default_config_path()
    
    if not config_src.exists():
        print(f"Warning: Default config not found at {config_src}")
        return False
    
    if config_dst.exists() and not force:
        print(f"Config already exists at {config_dst}")
        return False
    
    config_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config_src, config_dst)
    print(f"Installed config to {config_dst}")
    return True


def uninstall_plugin() -> bool:
    """Remove the LAAP plugin from OpenCode's plugins directory.
    
    Returns:
        True if removed successfully, False if not found.
    """
    plugin_dst = get_opencode_plugins_dir() / "laap-plugin.js"
    
    if not plugin_dst.exists():
        print(f"Plugin not found at {plugin_dst}")
        return False
    
    plugin_dst.unlink()
    print(f"Removed plugin from {plugin_dst}")
    return True


def install_all(force: bool = False) -> None:
    """Install both the plugin and config.
    
    Args:
        force: If True, overwrite existing files.
    """
    print("Installing LAAP OpenCode Plugin...")
    install_plugin(force)
    print("\nInstalling default config...")
    install_config(force)
    print("\nDone! Restart OpenCode to load the plugin.")


def uninstall_all() -> None:
    """Remove the plugin and config."""
    print("Uninstalling LAAP OpenCode Plugin...")
    uninstall_plugin()
    print("\nDone!")
