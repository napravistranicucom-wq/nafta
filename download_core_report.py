#!/usr/bin/env python3
"""Download PDFs/images linked from a USGS core report page.

Example:
  python download_core_report.py --url https://my.usgs.gov/crcwc/core/report/15887 --out ./docs

If the site requires auth, pass a Cookie header you already have:
  python download_core_report.py --url ... --out ./docs --cookie "JSESSIONID=...; other=..."
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ASSET_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "a" and attrs_d.get("href"):
            self.links.append(attrs_d["href"])
        if tag.lower() == "img" and attrs_d.get("src"):
            self.links.append(attrs_d["src"])


def _safe_filename(name: str) -> str:
    name = name.strip().strip("/\\")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "download"


def _guess_filename(url: str, content_disposition: str | None) -> str:
    if content_disposition:
        # basic filename= extraction
        m = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, flags=re.I)
        if m:
            return _safe_filename(m.group(1))
        m = re.search(r"filename=\"?([^;\"]+)\"?", content_disposition, flags=re.I)
        if m:
            return _safe_filename(m.group(1))

    p = urlparse(url)
    base = os.path.basename(p.path)
    if base:
        return _safe_filename(base)
    return "download"


def iter_asset_links(page_url: str, html: str) -> Iterable[str]:
    parser = LinkParser()
    parser.feed(html)

    for raw in parser.links:
        if not raw:
            continue
        u = urljoin(page_url, raw)
        pu = urlparse(u)
        if not pu.scheme.startswith("http"):
            continue

        # direct by extension
        ext = Path(pu.path).suffix.lower()
        if ext in ASSET_EXTS:
            yield u
            continue

        # heuristics for download endpoints
        if "download" in pu.path.lower() or "attachment" in pu.path.lower():
            yield u
            continue


def download(url: str, out_dir: Path, headers: dict[str, str]) -> Path | None:
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=60) as r:
            cd = r.headers.get("content-disposition")
            ct = (r.headers.get("content-type") or "").lower()
            data = r.read()

        name = _guess_filename(url, cd)

        # If server sends html, skip (likely not an asset)
        if "text/html" in ct and not name.lower().endswith(tuple(ASSET_EXTS)):
            return None

        out_path = out_dir / name
        # avoid overwrite collisions
        if out_path.exists() and out_path.read_bytes() == data:
            return out_path

        if out_path.exists():
            stem = out_path.stem
            suffix = out_path.suffix
            i = 2
            while True:
                cand = out_dir / f"{stem}_{i}{suffix}"
                if not cand.exists():
                    out_path = cand
                    break
                i += 1

        out_path.write_bytes(data)
        return out_path
    except Exception:
        return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Download PDFs/images linked from a core report page")
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True, help="Output folder")
    ap.add_argument("--cookie", default=None, help="Cookie header value if auth is required")
    ap.add_argument("--same-host", action="store_true", help="Only download links from the same host")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "Mozilla/5.0"}
    if args.cookie:
        headers["Cookie"] = args.cookie

    # fetch page html
    req = Request(args.url, headers=headers)
    with urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", errors="ignore")

    host = urlparse(args.url).netloc

    links = sorted(set(iter_asset_links(args.url, html)))
    if args.same_host:
        links = [u for u in links if urlparse(u).netloc == host]

    wrote = 0
    for u in links:
        p = download(u, out_dir, headers=headers)
        if p:
            wrote += 1
            print(f"saved {p}")

    print(f"found links: {len(links)}")
    print(f"downloaded: {wrote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
