# Doom Tool

Modular downloader/installer framework for Doom games (I and II) and related mods.

## Important

This project only supports downloading from URLs you provide (or from manifests you curate). Do not include pirated/copyright-infringing sources.

## Run

From the project folder:

```powershell
py -m doom_tool.main --help
```

To test end-to-end with placeholders (no Doom binaries included), run:

```powershell
py -m doom_tool.main --dry-run --verbose
py -m doom_tool.main --verbose
```

Replace `config/sources.doom1.manifest.json` and `config/sources.doom2.manifest.json` with URLs you provide (assumed legal/authorized).

This is a work in progress, however currently it supports Doom 1 & Doom 2
