"""Melo AI — FastAPI backend exposing a KNN song-recommendation model."""
from __future__ import annotations

import ctypes
import ctypes.util
import gc
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "danceability",
    "energy",
    "key",
    "loudness",
    "mode",
    "speechiness",
    "acousticness",
    "instrumentalness",
    "liveness",
    "valence",
    "tempo",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _pick_dataset() -> Path:
    """Prefer the 500k CSV if present, fall back to the original 268k file."""
    for candidate in (DATA_DIR / "mainDB_500k.csv", DATA_DIR / "mainDB.csv"):
        if candidate.exists():
            return candidate
    raise RuntimeError("No dataset file found in data/")


DATA_PATH = _pick_dataset()

# Map curly/smart punctuation to ASCII so user input matches dataset entries.
_PUNCT_NORMALIZE = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "―": "-",
    " ": " ",
})


def _normalize(text: str) -> str:
    return text.translate(_PUNCT_NORMALIZE).strip().lower()


def _release_unused_memory() -> None:
    """Ask glibc to hand freed memory back to the OS. No-op outside Linux."""
    gc.collect()
    libc_path = ctypes.util.find_library("c")
    if not libc_path:
        return
    try:
        libc = ctypes.CDLL(libc_path)
        if hasattr(libc, "malloc_trim"):
            libc.malloc_trim(0)
    except OSError:
        pass


state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not DATA_PATH.exists():
        raise RuntimeError(f"Dataset not found at {DATA_PATH}")

    available = pd.read_csv(DATA_PATH, nrows=0).columns
    cols = ["song_name", "artist", *FEATURE_COLS]
    if "popularity" in available:
        cols.append("popularity")
    if "release_year" in available:
        cols.append("release_year")

    # Chunked CSV load to bound peak working set during parsing.
    feature_dtypes = {col: np.float32 for col in FEATURE_COLS}
    chunks = []
    for chunk in pd.read_csv(
        DATA_PATH,
        usecols=cols,
        dtype=feature_dtypes,
        chunksize=100_000,
    ):
        chunk = chunk.dropna(subset=FEATURE_COLS + ["song_name", "artist"])
        chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)
    del chunks
    gc.collect()

    if "popularity" not in df.columns:
        # The 500k Kaggle build has no popularity column. Derive a 0–100 rank
        # from row order — the build script sorts by year desc, so this puts
        # recent tracks at the top, which is what autocomplete should show.
        ranks = 100 - (100 * np.arange(len(df), dtype=np.float32) / max(1, len(df) - 1))
        df["popularity"] = ranks.astype(np.int16)
    else:
        df["popularity"] = df["popularity"].astype(np.int16)

    if "release_year" in df.columns:
        df["release_year"] = df["release_year"].fillna(0).astype("int16")

    # Convert the heavy string columns: Arrow-backed for song_name (high
    # cardinality, ~3× less memory than Python object strings), Categorical
    # for artist (heavy repeats compress to codes + lookup table).
    df["song_name"] = df["song_name"].astype("string[pyarrow]")
    df["artist"] = df["artist"].astype(str).astype("category")

    # Precomputed lowercased name for /search and /recommend. Storing it
    # explicitly costs ~40 MB but is cheaper than lazy lowercase: pandas
    # holds onto temporary string buffers across requests, which inflates
    # the process by 200+ MB under sustained traffic.
    df["song_name_lower"] = (
        df["song_name"].astype(str).map(_normalize).astype("string[pyarrow]")
    )

    gc.collect()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[FEATURE_COLS].to_numpy()).astype(np.float32)

    knn = NearestNeighbors(n_neighbors=11, metric="cosine", algorithm="brute")
    knn.fit(X_scaled)

    # X_scaled now holds the model input; drop the per-row feature columns we
    # don't need to return in the response. The frontend only renders bars for
    # danceability/energy/valence/tempo — keeping just those saves ~14 MB.
    display_features = {"danceability", "energy", "valence", "tempo"}
    drop_features = [c for c in FEATURE_COLS if c not in display_features]
    if drop_features:
        df = df.drop(columns=drop_features)
    _release_unused_memory()

    state["df"] = df
    state["X_scaled"] = X_scaled
    state["knn"] = knn
    state["data_path"] = str(DATA_PATH.name)
    yield
    state.clear()


app = FastAPI(title="Melo AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    track_name: str = Field(..., min_length=1)
    artist_name: Optional[str] = ""
    # 0 means "any era" (no filter). Otherwise, results must be within
    # ±max_year_diff calendar years of the input song's release year.
    max_year_diff: int = Field(default=0, ge=0, le=100)


class Song(BaseModel):
    name: str
    artist: str
    spotify_search_url: str
    similarity: float
    features: dict[str, float]
    release_year: Optional[int] = None


class RecommendResponse(BaseModel):
    input_song: Song
    recommendations: list[Song]


class SearchHit(BaseModel):
    name: str
    artist: str
    popularity: int


class SearchResponse(BaseModel):
    results: list[SearchHit]


def _spotify_search_url(name: str, artist: str) -> str:
    q = urllib.parse.quote(f"{name} {artist}".strip())
    return f"https://open.spotify.com/search/{q}"


_DISPLAY_FEATURES = ("danceability", "energy", "valence", "tempo")


def _row_to_song(row: pd.Series, similarity: float) -> Song:
    year_raw = row["release_year"] if "release_year" in row.index else None
    year_val: Optional[int]
    if year_raw is None or pd.isna(year_raw) or int(year_raw) == 0:
        year_val = None
    else:
        year_val = int(year_raw)
    return Song(
        name=str(row["song_name"]),
        artist=str(row["artist"]),
        spotify_search_url=_spotify_search_url(str(row["song_name"]), str(row["artist"])),
        similarity=round(float(similarity), 4),
        features={col: float(row[col]) for col in _DISPLAY_FEATURES if col in row.index},
        release_year=year_val,
    )


def _narrow_by_artist(df: pd.DataFrame, candidate_idx: np.ndarray, artist_q: str) -> np.ndarray:
    """Filter candidate row indices to those whose normalized artist matches."""
    if candidate_idx.size == 0 or not artist_q:
        return candidate_idx
    artists = df.loc[candidate_idx, "artist"].astype(str).map(_normalize).to_numpy()
    return candidate_idx[artists == artist_q]


@app.get("/api/search", response_model=SearchResponse)
def search(q: str, limit: int = 10) -> SearchResponse:
    df: pd.DataFrame = state["df"]

    query = _normalize(q)
    if len(query) < 2:
        return SearchResponse(results=[])

    limit = max(1, min(limit, 25))

    mask = df["song_name_lower"].str.contains(query, regex=False, na=False)
    candidates = df.loc[mask, ["song_name", "artist", "popularity"]]
    if candidates.empty:
        return SearchResponse(results=[])

    top = candidates.sort_values("popularity", ascending=False).head(limit)
    results = [
        SearchHit(
            name=str(row.song_name),
            artist=str(row.artist),
            popularity=int(row.popularity),
        )
        for row in top.itertuples(index=False)
    ]
    return SearchResponse(results=results)


@app.get("/api/health")
def health() -> dict:
    df = state.get("df")
    return {
        "status": "ok",
        "dataset_size": int(0 if df is None else len(df)),
        "source": state.get("data_path", ""),
    }


@app.post("/api/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    df: pd.DataFrame = state["df"]
    X_scaled: np.ndarray = state["X_scaled"]
    knn: NearestNeighbors = state["knn"]

    name_q = _normalize(req.track_name)
    artist_q = _normalize(req.artist_name or "")

    exact_idx = df.index[df["song_name_lower"] == name_q].to_numpy()
    matches = _narrow_by_artist(df, exact_idx, artist_q)

    if matches.size == 0:
        # Loose substring fallback for minor punctuation/casing differences.
        loose_idx = df.index[
            df["song_name_lower"].str.contains(name_q, regex=False, na=False)
        ].to_numpy()
        matches = _narrow_by_artist(df, loose_idx, artist_q)

    if matches.size == 0:
        raise HTTPException(
            status_code=404,
            detail=f"'{req.track_name}' not found in the library. Try a different spelling.",
        )

    # If multiple matches, prefer the most popular one (or most recent, when
    # popularity was derived from row order).
    if matches.size > 1:
        popularities = df.loc[matches, "popularity"].to_numpy()
        idx = int(matches[int(np.argmax(popularities))])
    else:
        idx = int(matches[0])

    input_vec = X_scaled[idx].reshape(1, -1)

    # When the user wants an era filter, ask KNN for a wider candidate pool
    # and filter by year after. 200 candidates is plenty: cosine KNN over
    # 11 features at 500k rows runs in well under 100 ms even at k=200.
    want_year_filter = (
        req.max_year_diff > 0
        and "release_year" in df.columns
        and int(df.loc[idx, "release_year"]) > 0
    )
    k = 200 if want_year_filter else 11
    distances, indices = knn.kneighbors(input_vec, n_neighbors=k)

    raw_pairs = [
        (int(i), float(d))
        for i, d in zip(indices[0], distances[0])
        if int(i) != idx
    ]

    if want_year_filter:
        input_year = int(df.loc[idx, "release_year"])
        years = df.loc[[p[0] for p in raw_pairs], "release_year"].to_numpy()
        in_window = np.abs(years - input_year) <= req.max_year_diff
        # Years stored as 0 mean "unknown" — exclude from in-era results.
        in_window &= years > 0
        filtered = [p for p, ok in zip(raw_pairs, in_window) if ok][:10]
        # If the window is too tight to fill 10 slots, fall back to widening.
        if len(filtered) < 10:
            for widen in (req.max_year_diff * 2, req.max_year_diff * 4):
                widened = [
                    p
                    for p, y in zip(raw_pairs, years)
                    if y > 0 and abs(int(y) - input_year) <= widen
                ][:10]
                if len(widened) >= 10:
                    filtered = widened
                    break
            else:
                # As a last resort, fall back to pure audio similarity.
                filtered = raw_pairs[:10]
        pairs = filtered
    else:
        pairs = raw_pairs[:10]

    recommendations = [
        _row_to_song(df.iloc[i], similarity=1.0 - d) for i, d in pairs
    ]
    input_song = _row_to_song(df.iloc[idx], similarity=1.0)

    return RecommendResponse(input_song=input_song, recommendations=recommendations)
