from pathlib import Path
import os

APP_ID_DEFAULT = "io.github.quotezproject.quotez"

# Return True if running inside Flatpak
def is_flatpak() -> bool:
    return Path("/.flatpak-info").exists() or bool(os.environ.get("FLATPAK_ID"))

def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")

def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")

# Check whether app_id is already in the path parts
def _xdg_contains_app_id(xdg_path: Path, app_id: str) -> bool:
    try:
        return app_id in xdg_path.parts
    except Exception:
        return False

def _default_package_root(package_root: Path | None = None) -> Path:
    # Determine project root when package_root isn't provided
    if package_root is not None:
        return package_root.resolve()
    # derive based on this file being inside app/, fallback to cwd on error
    try:
        return Path(__file__).resolve().parents[1]
    except Exception:
        return Path.cwd().resolve()

# config file path (creates parent dir)
def get_config_file(
    filename: str = "settings.json",
    app_id: str = APP_ID_DEFAULT,
    package_root: Path | None = None,
) -> Path:
    # If running under Flatpak -> use XDG config, otherwise use project-local file
    if is_flatpak():
        xcfg = _xdg_config_home()
        if _xdg_contains_app_id(xcfg, app_id):
            cfg_dir = xcfg
        else:
            cfg_dir = xcfg / app_id

        cfg_dir.mkdir(parents=True, exist_ok=True)
        return (cfg_dir / filename).resolve()
    else:
        root = _default_package_root(package_root)
        cfg_path = (root / filename).resolve()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        return cfg_path

# data directory (creates it)
def get_data_dir(
    app_id: str = APP_ID_DEFAULT,
    package_root: Path | None = None,
    subdir: str = "quotez",
) -> Path:
    # If Flatpak -> use XDG per-app data dir, otherwise use project-local <project-root>/<subdir>
    if is_flatpak():
        xdata = _xdg_data_home()
        if _xdg_contains_app_id(xdata, app_id):
            base = xdata
        else:
            base = xdata / app_id

        data_dir = (base / subdir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    else:
        root = _default_package_root(package_root)
        data_dir = (root / subdir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

# Find resource: Flatpak /app/share, then package_root/assets, then cwd/assets
def get_resource_file(
    filename: str,
    package_root: Path | None = None,
    flatpak_share_subdir: str = "share/quotez"
) -> Path:
    # Search order: 1) /app/<flatpak_share_subdir>/<filename> 2) <project-root>/assets/<filename> 3) ./assets/<filename>
    try:
        flatpak_candidate = Path("/app") / Path(flatpak_share_subdir)
        fp = (flatpak_candidate / filename)
        if fp.exists():
            return fp.resolve()
    except Exception:
        pass

    root = _default_package_root(package_root)
    dev = (root / "assets" / filename)
    if dev.exists():
        return dev.resolve()

    cwdp = Path.cwd() / "assets" / filename
    return cwdp.resolve()