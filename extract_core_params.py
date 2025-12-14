#!/usr/bin/env python3
"""Extract common core-analysis parameters from PDFs/images into CSV/XLSX.

Typical inputs: lab reports, core analysis summaries, scanned tables.
Outputs:
- long CSV (one row per detected parameter)
- optional wide XLSX (one row per source doc/sample, columns per parameter)

Notes:
- PDF text extraction is attempted first; OCR is used when needed.
- OCR requires the system binary `tesseract`.

Usage example:
  python extract_core_params.py --input ./docs --out-long core_params_long.csv --out-wide core_params_wide.xlsx
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


# -------------------------
# Parameter patterns
# -------------------------

@dataclasses.dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str
    patterns: tuple[re.Pattern[str], ...]


def _rx(p: str) -> re.Pattern[str]:
    return re.compile(p, flags=re.IGNORECASE | re.MULTILINE)


PARAM_SPECS: tuple[ParamSpec, ...] = (
    ParamSpec(
        key="permeability",
        label="Permeability",
        patterns=(
            _rx(r"\b(?:perm(?:eability)?|k(?:\s*linkenberg)?|kair|k\s*air)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>m\s*d|md|millidarcy|darcy|d|\u00b5d|ud|m\^2)?"),
            _rx(r"\b(?:gas|air)\s*perm(?:eability)?\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>m\s*d|md|millidarcy|darcy|d|\u00b5d|ud)?"),
        ),
    ),
    ParamSpec(
        key="porosity",
        label="Porosity",
        patterns=(
            _rx(r"\b(?:poro(?:sity)?|\u03d5|phi)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>%|percent)?"),
            _rx(r"\b(?:effective\s*porosity|eff\.?\s*poro(?:sity)?)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>%|percent)?"),
        ),
    ),
    ParamSpec(
        key="grain_density",
        label="Grain density",
        patterns=(
            _rx(r"\b(?:grain\s*density|\u03c1\s*g)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>g\s*/\s*cc|g\s*/\s*cm\^3|g\s*cm-?3)?"),
        ),
    ),
    ParamSpec(
        key="bulk_density",
        label="Bulk density",
        patterns=(
            _rx(r"\b(?:bulk\s*density|\u03c1\s*b)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>g\s*/\s*cc|g\s*/\s*cm\^3|g\s*cm-?3)?"),
        ),
    ),
    ParamSpec(
        key="water_saturation",
        label="Water saturation",
        patterns=(
            _rx(r"\b(?:sw|s\s*w|water\s*saturation)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>%|percent)?"),
        ),
    ),
    ParamSpec(
        key="oil_saturation",
        label="Oil saturation",
        patterns=(
            _rx(r"\b(?:so|s\s*o|oil\s*saturation)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>%|percent)?"),
        ),
    ),
    ParamSpec(
        key="gas_saturation",
        label="Gas saturation",
        patterns=(
            _rx(r"\b(?:sg|s\s*g|gas\s*saturation)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>%|percent)?"),
        ),
    ),
    ParamSpec(
        key="net_confining_pressure",
        label="Net confining pressure",
        patterns=(
            _rx(r"\b(?:net\s*confining\s*pressure|ncp)\b\s*[:=]?\s*(?P<value>[-+]?\d+(?:[\.,]\d+)?)\s*(?P<unit>psi|kpa|mpa|bar)?"),
        ),
    ),
)


DEPTH_PATTERNS: tuple[re.Pattern[str], ...] = (
    _rx(r"\b(?:depth|core\s*depth)\b\s*[:=]?\s*(?P<value>\d+(?:[\.,]\d+)?)\s*(?P<unit>m|meter|metre|ft|feet)\b"),
    _rx(r"\b(?P<value>\d+(?:[\.,]\d+)?)\s*(?P<unit>m|ft)\b\s*(?:md|measured\s*depth)\b"),
)


# -------------------------
# Extraction helpers
# -------------------------

def _to_float(s: str) -> Optional[float]:
    s = s.strip().replace(" ", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norm_unit(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = re.sub(r"\s+", "", u.strip().lower())
    unit_map = {
        "md": "mD",
        "m*d": "mD",
        "millidarcy": "mD",
        "d": "D",
        "darcy": "D",
        "ud": "uD",
        "µd": "uD",
        "%": "%",
        "percent": "%",
        "g/cc": "g/cc",
        "g/cm^3": "g/cc",
        "gcm-3": "g/cc",
        "psi": "psi",
        "kpa": "kPa",
        "mpa": "MPa",
        "bar": "bar",
        "m": "m",
        "meter": "m",
        "metre": "m",
        "ft": "ft",
        "feet": "ft",
        "m^2": "m^2",
    }
    return unit_map.get(u, u)


def _snip(text: str, start: int, end: int, radius: int = 80) -> str:
    a = max(0, start - radius)
    b = min(len(text), end + radius)
    snippet = text[a:b]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet


def extract_depth(text: str) -> tuple[Optional[float], Optional[str]]:
    for rx in DEPTH_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        v = _to_float(m.group("value"))
        u = _norm_unit(m.group("unit"))
        return v, u
    return None, None


def iter_param_hits(text: str) -> Iterable[dict]:
    for spec in PARAM_SPECS:
        for rx in spec.patterns:
            for m in rx.finditer(text):
                raw_value = m.groupdict().get("value")
                raw_unit = m.groupdict().get("unit")
                value = _to_float(raw_value) if raw_value else None
                unit = _norm_unit(raw_unit)
                yield {
                    "parameter_key": spec.key,
                    "parameter": spec.label,
                    "value": value,
                    "unit": unit,
                    "raw_value": raw_value,
                    "raw_unit": raw_unit,
                    "context": _snip(text, m.start(), m.end()),
                }


# -------------------------
# File readers
# -------------------------

def read_text_from_pdf(path: Path, ocr: bool = True, max_pages: int | None = None) -> str:
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        pages = pdf.pages
        if max_pages is not None:
            pages = pages[:max_pages]

        for page in pages:
            txt = page.extract_text() or ""
            txt = txt.strip()
            if txt:
                chunks.append(txt)

    text = "\n\n".join(chunks)

    # If we extracted very little text, fall back to OCR page images.
    if ocr and len(text) < 400:
        try:
            import pytesseract
            from PIL import Image
            import pdfplumber

            ocr_chunks: list[str] = []
            with pdfplumber.open(str(path)) as pdf:
                pages = pdf.pages
                if max_pages is not None:
                    pages = pages[:max_pages]
                for page in pages:
                    pil_img: Image.Image = page.to_image(resolution=300).original
                    ocr_chunks.append(pytesseract.image_to_string(pil_img) or "")
            ocr_text = "\n\n".join(ocr_chunks)
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
        except Exception:
            # OCR is best-effort (missing tesseract, PIL issues, etc.)
            pass

    return text


def read_text_from_image(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(str(path))
        return pytesseract.image_to_string(img) or ""
    except Exception:
        return ""


def read_text(path: Path, ocr: bool = True, max_pages: int | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_text_from_pdf(path, ocr=ocr, max_pages=max_pages)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        return read_text_from_image(path)
    if suffix in {".txt"}:
        return path.read_text(errors="ignore")

    # Unsupported type
    return ""


# -------------------------
# Main
# -------------------------

def build_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    if long_df.empty:
        return long_df

    # Prefer the first non-null value per parameter per source.
    long_df = long_df.copy()
    long_df["value_str"] = long_df.apply(
        lambda r: "" if pd.isna(r.get("value")) else str(r.get("value")), axis=1
    )
    long_df["unit_str"] = long_df["unit"].fillna("")
    long_df["val_unit"] = (long_df["value_str"] + " " + long_df["unit_str"]).str.strip()

    wide = (
        long_df.sort_values(["source_file", "parameter_key"])
        .groupby(["source_file", "sample_id", "depth_value", "depth_unit", "parameter_key", "parameter"], as_index=False)
        .agg({"val_unit": "first"})
    )

    wide_pivot = wide.pivot_table(
        index=["source_file", "sample_id", "depth_value", "depth_unit"],
        columns=["parameter_key"],
        values="val_unit",
        aggfunc="first",
    ).reset_index()

    # Flatten columns
    wide_pivot.columns = [c if isinstance(c, str) else c[-1] for c in wide_pivot.columns]
    return wide_pivot


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Extract core-analysis parameters into CSV/XLSX")
    ap.add_argument("--input", required=True, help="Folder with PDFs/images")
    ap.add_argument("--out-long", default="core_params_long.csv", help="Output CSV (long format)")
    ap.add_argument("--out-wide", default=None, help="Output XLSX (wide format)")
    ap.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback")
    ap.add_argument("--max-pages", type=int, default=None, help="Max pages per PDF (for speed)")
    ap.add_argument("--pdf-only", action="store_true", help="Only scan PDFs (skip images)")

    args = ap.parse_args(argv)

    in_dir = Path(args.input)
    if not in_dir.exists() or not in_dir.is_dir():
        print(f"Input folder not found: {in_dir}", file=sys.stderr)
        return 2

    allowed_exts = {".pdf"} if args.pdf_only else {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".txt"}

    files: list[Path] = []
    for p in sorted(in_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in allowed_exts:
            files.append(p)

    rows: list[dict] = []

    for f in files:
        text = read_text(f, ocr=not args.no_ocr, max_pages=args.max_pages)
        text = text or ""
        depth_value, depth_unit = extract_depth(text)

        sample_id = f.stem

        any_hit = False
        for hit in iter_param_hits(text):
            any_hit = True
            rows.append(
                {
                    "source_file": str(f),
                    "sample_id": sample_id,
                    "depth_value": depth_value,
                    "depth_unit": depth_unit,
                    **hit,
                }
            )

        # Still emit a row so you can see which files had no matches.
        if not any_hit:
            rows.append(
                {
                    "source_file": str(f),
                    "sample_id": sample_id,
                    "depth_value": depth_value,
                    "depth_unit": depth_unit,
                    "parameter_key": None,
                    "parameter": None,
                    "value": None,
                    "unit": None,
                    "raw_value": None,
                    "raw_unit": None,
                    "context": None,
                }
            )

    long_df = pd.DataFrame(rows)
    long_df.to_csv(args.out_long, index=False)

    if args.out_wide:
        wide_df = build_wide(long_df[long_df["parameter_key"].notna()])
        with pd.ExcelWriter(args.out_wide, engine="openpyxl") as xw:
            wide_df.to_excel(xw, index=False, sheet_name="wide")
            long_df.to_excel(xw, index=False, sheet_name="long")

    print(f"Wrote: {args.out_long}")
    if args.out_wide:
        print(f"Wrote: {args.out_wide}")
    print(f"Scanned files: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
