from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from typing import IO
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from doom_tool.core.source_selector import SelectedSource


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_stream(url: str, out_path: Path, timeout_s: float = 60.0, verbose: bool = False) -> int | None:
    headers = {"User-Agent": "doom-tool/0.1"}
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=timeout_s) as resp:
        content_length = resp.headers.get("Content-Length")
        total = int(content_length) if content_length and content_length.isdigit() else None

        out_path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        downloaded = 0
        chunk_size = 1024 * 1024

        with out_path.open("wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if verbose and total:
                    pct = (downloaded / total) * 100
                    elapsed = max(time.time() - start, 0.001)
                    rate_mbps = (downloaded / (1024 * 1024)) / elapsed
                    print(f"[download] {out_path.name}: {pct:6.2f}% ({downloaded}/{total}) ~{rate_mbps:.2f} MiB/s")

    return total


def download_best_source(
    game_id: str,
    selected: SelectedSource,
    game_install_dir: Path,
    download_dir: Path,
    dry_run: bool,
    verbose: bool,
) -> None:
    cand = selected.candidate
    dl_path = download_dir / selected.resolved_filename
    install_dir = game_install_dir / game_id
    install_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"[doom-tool] {game_id} -> {cand.id} ({cand.url})")

    if dry_run:
        print(f"[doom-tool] DRY RUN: would download to {dl_path} and install into {install_dir}")
        return

    # Download if not present (or if checksum mismatches).
    if dl_path.exists() and cand.sha256:
        current = _sha256_file(dl_path)
        if current.lower() == cand.sha256.lower():
            if verbose:
                print(f"[download] Using cached file (sha256 ok): {dl_path.name}")
            # Skip re-download
        else:
            if verbose:
                print(f"[download] Cached sha256 mismatch; re-downloading: {dl_path.name}")
            dl_path.unlink(missing_ok=True)
    elif dl_path.exists():
        if verbose:
            print(f"[download] Using cached file: {dl_path.name}")
    else:
        if verbose:
            print(f"[download] Fetching: {dl_path.name}")

        _download_stream(cand.url, dl_path, verbose=verbose)

    # Verify sha256 if provided.
    if cand.sha256:
        current = _sha256_file(dl_path)
        if current.lower() != cand.sha256.lower():
            raise RuntimeError(f"sha256 mismatch for {game_id} download: expected {cand.sha256}, got {current}")

    # Install: if archive is zip, extract; else copy to install dir.
    if cand.archive == "zip":
        import zipfile

        # Extract into install dir; zip may include its own folder structure.
        if verbose:
            print(f"[install] Extracting zip into {install_dir}")
        # Clean target subfolder by removing only the extracted archive output? Keep simple: extract directly.
        with zipfile.ZipFile(dl_path) as zf:
            zf.extractall(install_dir)
    else:
        dst = install_dir / selected.resolved_filename
        if verbose:
            print(f"[install] Copying to {dst}")
        shutil.copy2(dl_path, dst)

