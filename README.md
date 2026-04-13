# QuoteZ — Quickly note & Zealously recall

A seamless way to capture, organize, and rediscover the quotes that resonate with you. Build and manage your personal collection with ease.

![Main view](github/screenshot-1.png)

---

## Features

### One-Click Actions
Streamline your workflow with instant access to essential tools. Copy quote text, edit existing entries, or remove outdated quotes with a single click.

### Multi-Speaker Quotes
Handle complex dialogues with ease. A single entry can capture interactions between multiple people, ensuring no part of the conversation is lost.

### Smart Grouping
Keep your library structured and intuitive. Organize your collection using person-specific categories and custom groups to find what matters most.

### Powerful Filtering
Navigate large collections without the noise. Quickly narrow down your entries by date, character length, specific people, or assigned groups.

## Build

Install required packages (Debian):

```bash
sudo apt install -y flatpak flatpak-builder git python3 python3-pip python3-venv build-essential python3-dev libffi-dev libssl-dev pkg-config curl
```

Make sure you have flathub setup:

```bash
sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

Install required packages (Flatpak):

```bash
flatpak-builder --force-clean --install-deps-from=flathub build-dir io.github.quotezproject.quotez.json
```

To build cd into the main directory and use the commands:

```bash
flatpak-builder --repo=flatpak/builder/repo --force-clean flatpak/builder/build flatpak/io.github.quotezproject.quotez.json
```

Create a flatpak file with:

```bash
flatpak build-bundle flatpak/builder/repo flatpak/builder/QuoteZ.flatpak io.github.quotezproject.quotez
```

## DISCLAIMER

This was fully vibe-coded, I do not know how to code!
