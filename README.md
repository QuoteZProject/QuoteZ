# QuoteZ — Smart, human-friendly quote management

QuoteZ is a lightweight app for taking and reading quotes. Add people, put them into groups, and create multi-speaker quotes. Designed for authors, podcasters, researchers, and anyone who collects spoken or written snippets.

---

## People & Groups

Create people, assign to multiple groups (e.g. characters, interviewees, team).

## Multi-Quote

Quotes can contain multiple speakers on the same line using repeated speaker tags; timestamps are required.

## Human-readable format

Uses QuoteZ’s own concise, human-readable single-line format for easy reading, diffing, and versioning.

## Advanced Search

Filter by newest/oldest, date range, character-length range, and keyword search with powerful operators (wildcards, AND/OR/NOT, grouping). Designed for fast, precise digging through big quote sets.

## Main view

![Main view](github/screenshot-1.png)

## Features

* **People** — create named people with optional notes and nicknames (aliases).
* **Groups** — group people into any number of groups (tags, casts, teams).
* **Multi-quote** — compose quotes with more than one speaker on the same line using repeated speaker tags; timestamps are required.
* **Nicknames on copy** — copying a quote uses the speaker’s nickname; if multiple nicknames exist, QuoteZ prompts you to choose.
* **Search & Filter** — search by text, person, group or date; filter multi-quote participants.

## Storage format

QuoteZ uses a concise, human-readable single-line record format with required timestamps and required URLs. The timestamp uses `yyyy-MM-dd;hhh:mm:ss`. The quote body supports multiple speakers via inline attribution.

## Multi-quote editor

QuoteZ multi-quote editor

## Examples & tips

* **Character notes:** Use groups for story casts so you can filter quotes per scene.
* **Interview transcripts:** Use multi-quote turns with timestamps to reconstruct the flow.
* **Source-linked quotes:** Every quote includes a required URL so you can jump back to the exact source (episode, page, timestamp).

## Build

To build cd into the main directory and use the commands:

```bash
flatpak-builder --repo=flatpak/builder/repo --force-clean flatpak/builder/build flatpak/io.github.quotezproject.quotez.json
```

Create a flatpak file with:

```bash
flatpak build-bundle flatpak/builder/repo flatpak/builder/QuoteZ.flatpak io.github.quotezproject.quotez
```
