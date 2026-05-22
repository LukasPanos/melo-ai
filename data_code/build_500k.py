"""Build a 500k-song mainDB from the Kaggle 1.2M Spotify tracks dataset.

Expects the Kaggle source file at data/tracks_features.csv after downloading
https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs

Writes data/mainDB_500k.csv in the same schema the backend uses.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SRC = DATA_DIR / "tracks_features.csv"
DST_CSV = DATA_DIR / "mainDB_500k.csv"
DST_PARQUET = DATA_DIR / "mainDB_500k.parquet"
TARGET_ROWS = 500_000

FEATURE_COLS = [
    "danceability", "energy", "key", "loudness", "mode",
    "speechiness", "acousticness", "instrumentalness",
    "liveness", "valence", "tempo",
]


def parse_first_artist(raw: object) -> str:
    """Kaggle stores artists as a Python list literal like \"['Taylor Swift']\"."""
    if not isinstance(raw, str):
        return ""
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)) and parsed:
                return str(parsed[0])
        except (ValueError, SyntaxError):
            pass
    return raw


def main() -> None:
    if not SRC.exists():
        print(f"ERROR: missing {SRC}", file=sys.stderr)
        print(
            "Download from https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Reading {SRC.name} …")
    df = pd.read_csv(SRC)
    print(f"  loaded {len(df):,} rows, columns: {list(df.columns)[:8]}…")

    if "name" in df.columns:
        df = df.rename(columns={"name": "song_name"})
    if "year" in df.columns and "release_year" not in df.columns:
        df = df.rename(columns={"year": "release_year"})

    if "song_name" not in df.columns:
        print("ERROR: source CSV has no 'name'/'song_name' column.", file=sys.stderr)
        sys.exit(1)

    if "artist" not in df.columns:
        if "artists" not in df.columns:
            print("ERROR: source CSV has no 'artist'/'artists' column.", file=sys.stderr)
            sys.exit(1)
        print("  flattening 'artists' list -> first artist")
        df["artist"] = df["artists"].map(parse_first_artist)

    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"ERROR: missing audio feature columns: {missing}", file=sys.stderr)
        sys.exit(1)

    if "popularity" not in df.columns:
        if "release_year" in df.columns:
            print("  NOTE: no 'popularity' column; sorting by release_year desc instead.")
            sort_col = "release_year"
        else:
            print("  NOTE: no 'popularity' or 'release_year'; taking first rows in file order.")
            sort_col = None
    else:
        sort_col = "popularity"

    keep = df.dropna(subset=FEATURE_COLS + ["song_name", "artist"])
    print(f"  {len(keep):,} after dropping NaN feature/identity rows")

    if sort_col is not None:
        keep = keep.sort_values(sort_col, ascending=False)
    keep = keep.head(TARGET_ROWS).reset_index(drop=True)
    print(f"  selected top {len(keep):,} rows")

    out_cols = ["song_name", "artist"]
    if "popularity" in keep.columns:
        out_cols.append("popularity")
    out_cols += FEATURE_COLS

    out = keep[out_cols].copy()
    out["song_name"] = out["song_name"].astype(str)
    out["artist"] = out["artist"].astype(str)

    # Parquet is what the backend actually loads — small, fast, low memory.
    try:
        out.to_parquet(DST_PARQUET, compression="snappy", index=False)
        size_mb = DST_PARQUET.stat().st_size / 1_000_000
        print(f"Wrote {DST_PARQUET.name} ({size_mb:.1f} MB)")
    except ImportError:
        print("NOTE: pyarrow not installed; skipping parquet output.")

    # CSV is kept as a human-readable fallback / portability format.
    out.to_csv(DST_CSV, index=False)
    size_mb = DST_CSV.stat().st_size / 1_000_000
    print(f"Wrote {DST_CSV.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
