#!/usr/bin/env python3
"""Copy only desktop files; back up every replaced file, including symlinks."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parent


def user_dir(home, name, fallback):
    if shutil.which("xdg-user-dir"):
        result = subprocess.run(["xdg-user-dir", name], capture_output=True, text=True,
                                env={**os.environ, "HOME": str(home)}, timeout=5)
        path = Path(result.stdout.strip())
        if result.returncode == 0 and path.is_absolute():
            return path
    return home / fallback


def settings(home, plugin_dir, wallpaper, pictures, videos):
    enabled = ["noctalia/wallhaven", "kenn/keybind-cheatsheet", "vn1k/cursor",
               "noctalia/notes", "vlad-dev/timer"]
    center = ["clock", "keybinds"]
    if shutil.which("gpu-screen-recorder") and shutil.which("slurp"):
        enabled.append("noctalia/screen_recorder")
        center.append("recorder")
    if shutil.which("easyeffects"):
        enabled.append("vlad-dev/equalizer")
        center.append("eq_widget")
    if shutil.which("mpvpaper"):
        enabled.append("noctalia/mpvpaper")
    replacements = {
        "PLUGIN_DIR": str(plugin_dir), "WALLPAPER": str(wallpaper),
        "PICTURES": str(pictures), "VIDEOS": str(videos),
        "WALLPAPERS": str(pictures / "Wallpapers"),
        "RENAME_SCRIPT": str(home / ".local/bin/noctalia-recorder-rename.sh"),
    }
    text = (ROOT / "local/state/noctalia/settings.toml").read_text()
    text = text.replace('["__PLUGINS__"]', json.dumps(enabled))
    text = text.replace('["__BAR_CENTER__"]', json.dumps(center))
    for key, value in replacements.items():
        text = text.replace(f'"__{key}__"', json.dumps(value, ensure_ascii=False))
    tomllib.loads(text)
    return text


def deploy(data, destination, mode, stamp, dry_run):
    exists = destination.exists() or destination.is_symlink()
    if destination.is_dir() and not destination.is_symlink():
        raise ValueError(f"Expected a file, found a directory: {destination}")
    print(f"{'[dry-run] ' if dry_run else ''}{destination}{' (backup)' if exists else ''}")
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if exists:
        backup = destination.with_name(destination.name + ".backup-" + stamp)
        if backup.exists() or backup.is_symlink():
            raise ValueError(f"Backup already exists: {backup}")
        shutil.copy2(destination, backup, follow_symlinks=False)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(data)
            file.flush()
            temporary.chmod(mode)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show paths, change nothing")
    parser.add_argument("--alacritty", action="store_true", help="also copy the optional terminal theme")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run as your normal user, not with sudo")
    if not shutil.which("niri"):
        parser.error("Install niri first (see README.md)")
    subprocess.run(["niri", "validate", "-c", str(ROOT / "config/niri/config.kdl")], check=True)
    home = Path.home()
    config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    state = Path(os.environ.get("XDG_STATE_HOME") or home / ".local/state")
    share = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    pictures = user_dir(home, "PICTURES", "Pictures")
    videos = user_dir(home, "VIDEOS", "Videos")
    plugins = share / "noctalia/dotfiles-plugins"
    wallpaper = share / "noctalia/dotfiles-wallpapers/wallhaven-og7p79.jpg"
    text = settings(home, plugins, wallpaper, pictures, videos)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    groups = [(ROOT / "noctalia-plugins", plugins),
              (ROOT / "local/bin", home / ".local/bin"),
              (ROOT / "config/noctalia", config / "noctalia")]
    if args.alacritty:
        groups.append((ROOT / "config/alacritty", config / "alacritty"))
    # niri reloads on write: its validated config is installed after its scripts.
    groups.append((ROOT / "config/niri", config / "niri"))
    for source, target in groups:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                executable = source.name == "bin" or path.name == "eqctl"
                deploy(path.read_bytes(), target / path.relative_to(source),
                       0o755 if executable else 0o644, stamp, args.dry_run)
    deploy((ROOT / "assets/wallhaven-og7p79.jpg").read_bytes(), wallpaper, 0o644, stamp, args.dry_run)
    deploy(text.encode(), state / "noctalia/settings.toml", 0o644, stamp, args.dry_run)
    if not args.dry_run:
        for directory in (pictures, videos, pictures / "Wallpapers"):
            directory.mkdir(parents=True, exist_ok=True)
    print("Done. Review niri/apps.conf; select the niri session at your next login.")
    print("VPN stays disabled. Backups: <filename>.backup-" + stamp)


if __name__ == "__main__":
    main()
