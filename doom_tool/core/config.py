from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GameConfig:
    game_id: str


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    download_dir: Path
    install_dir: Path
    games: list[str]
    game_map: dict[str, GameConfig]
    sources_manifests: dict[str, Path]
    mods_manifest: str
    dm_bat: Path

    def resolve_sources_manifest(self, game_id: str) -> Path:
        if game_id not in self.sources_manifests:
            raise KeyError(f"No sources manifest configured for game '{game_id}'")
        return self.sources_manifests[game_id]

    def run_dm_bat(self, dry_run: bool) -> None:
        # dm.bat is a placeholder hook that can be filled later to integrate your build/DM logic.
        if dry_run:
            return

        if not self.dm_bat.exists():
            raise FileNotFoundError(f"dm.bat not found: {self.dm_bat}")

        subprocess.run(["cmd", "/c", str(self.dm_bat)], cwd=str(self.root_dir), check=False)


def _resolve_path(root_dir: Path, p: str | Path) -> Path:
    pp = Path(p)
    if pp.is_absolute():
        return pp
    return (root_dir / pp).resolve()


def load_config(config_path: Path) -> AppConfig:
    config_path = config_path.resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    root_dir = config_path.parent.parent.resolve()  # doom-tool/

    raw: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))

    games = list(raw.get("games") or [])
    if not games:
        raise ValueError("config/settings.json must include a non-empty 'games' array")

    download_dir = _resolve_path(root_dir, raw.get("download_dir", "downloads"))
    install_dir = _resolve_path(root_dir, raw.get("install_dir", "games"))

    sources_manifests_raw: dict[str, Any] = raw.get("sources_manifests") or {}
    if not sources_manifests_raw:
        raise ValueError("config/settings.json must include 'sources_manifests' mapping")

    sources_manifests: dict[str, Path] = {}
    for game_id, p in sources_manifests_raw.items():
        sources_manifests[str(game_id)] = _resolve_path(root_dir, p)

    mods_manifest_raw = raw.get("mods_manifest", "config/mods.manifest.json")
    if isinstance(mods_manifest_raw, str) and (mods_manifest_raw.startswith("http://") or mods_manifest_raw.startswith("https://")):
        mods_manifest = mods_manifest_raw
    else:
        mods_manifest = str(_resolve_path(root_dir, mods_manifest_raw))
    dm_bat = _resolve_path(root_dir, raw.get("dm_bat", "modules/dm.bat"))

    game_map = {gid: GameConfig(game_id=gid) for gid in games}

    # Create dirs eagerly so later steps can assume they exist.
    download_dir.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        root_dir=root_dir,
        download_dir=download_dir,
        install_dir=install_dir,
        games=games,
        game_map=game_map,
        sources_manifests=sources_manifests,
        mods_manifest=mods_manifest,
        dm_bat=dm_bat,
    )

