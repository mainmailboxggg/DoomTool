from __future__ import annotations

import argparse
import json
from pathlib import Path

from doom_tool.core.config import AppConfig, load_config
from doom_tool.core.source_selector import SourceSelector
from doom_tool.core.downloader import download_best_source
from doom_tool.mods.manager import ModsManager


def _default_config_path() -> Path:
    return Path("config") / "settings.json"


def main() -> None:
    parser = argparse.ArgumentParser(prog="doom-tool", description="Doom I/II downloader + mod installer framework")
    parser.add_argument("--config", type=Path, default=_default_config_path(), help="Path to config/settings.json")
    parser.add_argument("--dry-run", action="store_true", help="Do not download, only validate candidates")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    cfg: AppConfig = load_config(args.config)

    if args.verbose:
        print(f"[doom-tool] Using config: {args.config.resolve()}")

    selector = SourceSelector(cfg)

    # Download games
    for game_id in cfg.games:
        game_cfg = cfg.game_map.get(game_id)
        if not game_cfg:
            raise SystemExit(f"No game config found for '{game_id}'")

        if args.verbose:
            print(f"[doom-tool] Selecting source for {game_id} ...")

        manifest_path = cfg.resolve_sources_manifest(game_id)
        selected = selector.select_from_manifest(game_id=game_id, manifest_path=manifest_path)

        download_best_source(
            game_id=game_id,
            selected=selected,
            game_install_dir=cfg.install_dir,
            download_dir=cfg.download_dir,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

    # Install mods
    mods = ModsManager(cfg, verbose=args.verbose)
    mods.install_all(dry_run=args.dry_run)

    # Call dm.bat placeholder (only first successful run)
    cfg.run_dm_bat(dry_run=args.dry_run, verbose=args.verbose)

    # Summarize
    if args.verbose:
        print("[doom-tool] Done.")


if __name__ == "__main__":
    main()

