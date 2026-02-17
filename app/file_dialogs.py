from PySide6.QtWidgets import QFileDialog
import shutil
import subprocess


def select_file_native(parent, title: str, filters: str) -> str | None:
    # Open system file picker, fall back to Qt
    glob_filters = "*.png *.jpg *.jpeg *.webp"

    # zenity
    if shutil.which("zenity"):
        try:
            proc = subprocess.run(
                [
                    "zenity", "--file-selection",
                    "--title", title,
                    "--file-filter", f"Images | {glob_filters}"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True
            )
            path = proc.stdout.strip()
            return path or None
        except subprocess.CalledProcessError:
            return None

    # kdialog
    if shutil.which("kdialog"):
        try:
            proc = subprocess.run(
                [
                    "kdialog", "--getopenfilename", "",
                    glob_filters,
                    "--title", title
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True
            )
            path = proc.stdout.strip()
            return path or None
        except subprocess.CalledProcessError:
            return None

    # Qt fallback
    path, _ = QFileDialog.getOpenFileName(parent, title, "", filters)
    return path or None


def select_folder_native(parent, title: str, start_dir: str = "") -> str | None:
    # Open system folder picker, fall back to Qt
    # zenity
    if shutil.which("zenity"):
        try:
            proc = subprocess.run(
                [
                    "zenity", "--file-selection",
                    "--directory",
                    "--title", title,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True
            )
            path = proc.stdout.strip()
            return path or None
        except subprocess.CalledProcessError:
            return None

    # kdialog
    if shutil.which("kdialog"):
        try:
            proc = subprocess.run(
                [
                    "kdialog", "--getexistingdirectory",
                    start_dir or ".",
                    "--title", title,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True
            )
            path = proc.stdout.strip()
            return path or None
        except subprocess.CalledProcessError:
            return None

    # Qt fallback
    path = QFileDialog.getExistingDirectory(parent, title, start_dir)
    return path or None