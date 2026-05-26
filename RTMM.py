#!/usr/bin/env python3
"""
Warhammer 40,000: Rogue Trader Mod Manager
Run: python3 rt_mod_manager.py <command> [args]
"""

import sys
import zipfile
import json
import shutil
import urllib.request
import urllib.error
from pathlib import Path

# === CONFIG ===
GAME_PREFIX = Path("/media/rory/RDR2/Warhammer 40,000 - Rogue Trader/rogue_trader_prefix")
MODS_DIR = GAME_PREFIX / "drive_c" / "users" / "rory" / "AppData" / "LocalLow" / "Owlcat Games" / "Warhammer 40000 Rogue Trader" / "Modifications"

# Nexus Mods API (get key from https://www.nexusmods.com/)
NEXUS_API_KEY = ""  # <-- Put your API key here
NEXUS_MOD_ID = 43231  # Warhammer 40,000: Rogue Trader Nexus Mods page

# For testing in Docker (dummy folder)
TEST_MODE = False
if TEST_MODE:
    MODS_DIR = Path("/work/test_mods")

# =====================
# Helper functions
# =====================

def confirm(action: str, default: bool = False) -> bool:
    """Ask user to confirm before doing something."""
    if TEST_MODE:
        print(f"  [auto-confirmed] {action}")
        return True
    try:
        response = input(f"{action} (yes/no): ").strip().lower()
        return response in ("yes", "y")
    except EOFError:
        return default

def download_file(url: str, dest: Path) -> bool:
    """Download a file from url to dest. Returns True on success."""
    print(f"  Downloading: {url}")
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False

# =====================
# COMMAND: list
# =====================

def cmd_list():
    """List all installed mods and their status."""
    if not MODS_DIR.exists():
        print(f"Mods folder not found: {MODS_DIR}")
        if confirm("Create it"):
            MODS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Created: {MODS_DIR}")
        return

    print(f"\nInstalled mods in: {MODS_DIR}\n")
    mods = sorted([d for d in MODS_DIR.iterdir() if d.is_dir()])

    if not mods:
        print("No mods installed.")
        return

    for mod in mods:
        disabled = mod.name.endswith(".disabled")
        status = "DISABLED" if disabled else "enabled"
        mod_name = mod.name[:-10] if disabled else mod.name
        print(f"  [{status}] {mod_name}")

    print(f"\nTotal: {len(mods)} mods")

# =====================
# COMMAND: install
# =====================

def cmd_install(zip_path: str):
    """Install a mod from a .zip file."""
    zip_file = Path(zip_path)

    if not zip_file.exists():
        print(f"File not found: {zip_path}")
        return

    if not str(zip_file).endswith(".zip"):
        print("Please provide a .zip file.")
        return

    print(f"Installing: {zip_file.name}")

    temp_dir = Path("/tmp/rt_mod_install")
    temp_dir.mkdir(exist_ok=True)

    try:
        with zipfile.ZipFile(zip_file, 'r') as zf:
            zf.extractall(temp_dir)

        contents = [f for f in temp_dir.iterdir() if f.is_dir()]
        if len(contents) == 1:
            mod_name = contents[0].name
        else:
            mod_name = zip_file.stem

        dest = MODS_DIR / mod_name

        if dest.exists():
            print(f"Mod already exists: {mod_name}")
            if not confirm(f"Overwrite {mod_name}?"):
                print("Cancelled.")
                return
            shutil.rmtree(dest)

        if len(contents) == 1:
            shutil.copytree(contents[0], dest)
        else:
            dest.mkdir(exist_ok=True)
            for item in temp_dir.iterdir():
                dest_item = dest / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item)
                else:
                    shutil.copy2(item, dest_item)

        print(f"Installed: {mod_name}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# =====================
# COMMAND: enable / disable
# =====================

def cmd_toggle(mod_name: str, enable: bool):
    """Enable or disable a mod by renaming."""
    mods = [d for d in MODS_DIR.iterdir() if d.is_dir() and d.name.startswith(mod_name)]

    if not mods:
        print(f"Mod not found: {mod_name}")
        return

    mod = mods[0]
    current_disabled = mod.name.endswith(".disabled")

    if enable and not current_disabled:
        print(f"Mod is already enabled: {mod.name}")
        return

    if not enable and current_disabled:
        print(f"Mod is already disabled: {mod.name}")
        return

    if confirm(f"{ 'Enable' if enable else 'Disable' } mod '{mod.name}'?"):
        new_name = mod.name[:-10] if current_disabled else mod.name + ".disabled"
        mod.rename(MODS_DIR / new_name)
        print(f"Mod {new_name}")
    else:
        print("Cancelled.")

# =====================
# COMMAND: remove
# =====================

def cmd_remove(mod_name: str):
    """Remove a mod completely."""
    mods = [d for d in MODS_DIR.iterdir() if d.is_dir() and d.name.startswith(mod_name)]

    if not mods:
        print(f"Mod not found: {mod_name}")
        return

    mod = mods[0]
    if confirm(f"Delete mod '{mod.name}' permanently?"):
        shutil.rmtree(mod)
        print(f"Deleted: {mod.name}")
    else:
        print("Cancelled.")

# =====================
# COMMAND: check
# =====================

def cmd_check():
    """Check mod dependencies from Info.json files."""
    print(f"Checking mods in: {MODS_DIR}\n")

    for mod_dir in sorted(MODS_DIR.iterdir()):
        if not mod_dir.is_dir():
            continue

        info_file = mod_dir / "Info.json"
        if not info_file.exists():
            continue

        try:
            with open(info_file) as f:
                info = json.load(f)

            required = info.get("requiredMod", [])
            if required:
                print(f"{mod_dir.name} requires: {required}")
        except Exception as e:
            print(f"Error reading {info_file}: {e}")

# =====================
# COMMAND: nexus-search
# =====================

def cmd_nexus_search(query: str):
    """Search Nexus Mods for Rogue Trader mods."""
    if not NEXUS_API_KEY:
        print("Nexus API key not set. Edit the script and add your key.")
        print("Get your key from: https://www.nexusmods.com/")
        return

    # Nexus Mods API v2 - search
    url = f"https://api.nexusmods.com/v2/search?q={query}&section=mods&category=3&sorting=relevance&limit=10"
    headers = {"apikey": NEXUS_API_KEY}

    print(f"\nSearching Nexus Mods for: {query}\n")

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.load(response)

        if "data" not in data or not data["data"]:
            print("No results found.")
            return

        for mod in data["data"]:
            mod_id = mod["id"]
            name = mod["attributes"]["name"]
            description = mod["attributes"].get("description", "")[:100]
            files = mod["attributes"].get("files", [])
            file_count = len(files)
            print(f"\n  [{mod_id}] {name}")
            print(f"    Files: {file_count}")
            print(f"    {description}...")

    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e.code} - {e.reason}")
    except Exception as e:
        print(f"Error: {e}")

# =====================
# COMMAND: nexus-download
# =====================

def cmd_nexus_download(mod_id: str, file_id: str = None):
    """Download a mod from Nexus Mods."""
    if not NEXUS_API_KEY:
        print("Nexus API key not set. Edit the script and add your key.")
        return

    if not file_id:
        # Get latest file
        url = f"https://api.nexusmods.com/v2/mods/{mod_id}"
        headers = {"apikey": NEXUS_API_KEY}

        print(f"Getting file info for mod {mod_id}...")

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.load(response)

            files = data["data"]["attributes"]["files"]
            if not files:
                print("No files found for this mod.")
                return

            # Pick the first file (usually the main download)
            file_id = files[0]["id"]
            print(f"Selected file {file_id}: {files[0]['attributes']['name']}")

        except Exception as e:
            print(f"Error: {e}")
            return

    # Download the file
    download_url = f"https://api.nexusmods.com/v2/files/{file_id}/download"
    headers = {"apikey": NEXUS_API_KEY}

    zip_path = MODS_DIR.parent / f"nexus_download_{file_id}.zip"

    req = urllib.request.Request(download_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(zip_path, "wb") as f:
                f.write(response.read())

        print(f"Downloaded to: {zip_path}")

        # Auto-install
        if confirm(f"Install {zip_path.name}?"):
            cmd_install(str(zip_path))
            # Clean up
            zip_path.unlink(missing_ok=True)

    except Exception as e:
        print(f"Download failed: {e}")

# =====================
# MAIN
# =====================

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 rt_mod_manager.py <command> [args]")
        print("\nCommands:")
        print("  list                      - Show all installed mods")
        print("  install <zip_file>        - Install a mod from .zip")
        print("  enable <mod_name>         - Enable a mod")
        print("  disable <mod_name>        - Disable a mod")
        print("  remove <mod_name>         - Delete a mod")
        print("  check                     - Check mod dependencies")
        print("  nexus-search <query>      - Search Nexus Mods")
        print("  nexus-download <mod_id>   - Download mod from Nexus")
        print("\nNote: Set NEXUS_API_KEY in the script first.")
        return

    command = sys.argv[1]

    if command == "list":
        cmd_list()
    elif command == "install":
        if len(sys.argv) < 3:
            print("Usage: python3 rt_mod_manager.py install <zip_file>")
        else:
            cmd_install(sys.argv[2])
    elif command == "enable":
        if len(sys.argv) < 3:
            print("Usage: python3 rt_mod_manager.py enable <mod_name>")
        else:
            cmd_toggle(sys.argv[2], True)
    elif command == "disable":
        if len(sys.argv) < 3:
            print("Usage: python3 rt_mod_manager.py disable <mod_name>")
        else:
            cmd_toggle(sys.argv[2], False)
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: python3 rt_mod_manager.py remove <mod_name>")
        else:
            cmd_remove(sys.argv[2])
    elif command == "check":
        cmd_check()
    elif command == "nexus-search":
        if len(sys.argv) < 3:
            print("Usage: python3 rt_mod_manager.py nexus-search <query>")
        else:
            cmd_nexus_search(sys.argv[2])
    elif command == "nexus-download":
        if len(sys.argv) < 3:
            print("Usage: python3 rt_mod_manager.py nexus-download <mod_id> [file_id]")
        else:
            cmd_nexus_download(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
