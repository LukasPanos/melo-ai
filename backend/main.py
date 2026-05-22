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
    """Use the curated 268k dataset. The 500k Kaggle build is kept around for
    experimentation but blows the 512 MB free-tier ceiling and has no real
    Spotify popularity, so it's not the default."""
    for candidate in (DATA_DIR / "mainDB.csv", DATA_DIR / "mainDB_500k.csv"):
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
    genre_cols_present = [c for c in ("genre_1", "genre_2", "genre_3") if c in available]
    cols.extend(genre_cols_present)

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

    # Normalize genres to lowercase Categoricals at load time so per-request
    # comparison is a cheap code lookup rather than a string scan.
    for col in genre_cols_present:
        df[col] = (
            df[col].fillna("").astype(str).str.strip().str.lower().astype("category")
        )

    # Artist becomes Categorical because the column has heavy repeats (codes
    # + lookup table is ~10× smaller than object strings).
    df["song_name"] = df["song_name"].astype(str)
    df["artist"] = df["artist"].astype(str).astype("category")

    # Precomputed lowercased name for /search and /recommend (lazy lowercase
    # bloats process memory under sustained traffic from pandas' temporary
    # string buffers).
    df["song_name_lower"] = df["song_name"].astype(str).map(_normalize)

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


class Song(BaseModel):
    name: str
    artist: str
    spotify_search_url: str
    similarity: float
    features: dict[str, float]
    release_year: Optional[int] = None
    genre: Optional[str] = None


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

    genre_val: Optional[str] = None
    for col in ("genre_1", "genre_2", "genre_3"):
        if col in row.index:
            v = row[col]
            if isinstance(v, str) and v.strip():
                genre_val = v
                break

    return Song(
        name=str(row["song_name"]),
        artist=str(row["artist"]),
        spotify_search_url=_spotify_search_url(str(row["song_name"]), str(row["artist"])),
        similarity=round(float(similarity), 4),
        features={col: float(row[col]) for col in _DISPLAY_FEATURES if col in row.index},
        release_year=year_val,
        genre=genre_val,
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

    input_vec = X_scaled[idx]

    # Try the genre-constrained path first: gather every song that shares at
    # least one of the input's three genres, then rank that subset by audio
    # cosine similarity. This matches the prototype's intent — KNN purely on
    # audio features tends to cross genre boundaries (pop song -> classical
    # piano with similar BPM/loudness), which makes recommendations feel off.
    genre_cols = [c for c in ("genre_1", "genre_2", "genre_3") if c in df.columns]
    pairs = _genre_filtered_top10(df, X_scaled, idx, input_vec, genre_cols)

    if pairs is None:
        # No usable genres on the input, or fewer than 10 in-genre candidates —
        # fall back to plain audio-only KNN so the user still gets results.
        distances, indices = knn.kneighbors(input_vec.reshape(1, -1))
        pairs = [
            (int(i), float(d))
            for i, d in zip(indices[0], distances[0])
            if int(i) != idx
        ][:10]

    recommendations = [
        _row_to_song(df.iloc[i], similarity=1.0 - d) for i, d in pairs
    ]
    input_song = _row_to_song(df.iloc[idx], similarity=1.0)

    return RecommendResponse(input_song=input_song, recommendations=recommendations)


def _genre_filtered_top10(
    df: pd.DataFrame,
    X_scaled: np.ndarray,
    input_idx: int,
    input_vec: np.ndarray,
    genre_cols: list[str],
) -> Optional[list[tuple[int, float]]]:
    """Return the top-10 most audio-similar songs that share a genre with the
    input. Returns None if there's no usable genre data or fewer than 10
    matches (caller falls back to plain KNN)."""
    if not genre_cols:
        return None

    input_row = df.iloc[input_idx]
    input_genres: set[str] = set()
    for col in genre_cols:
        v = input_row[col]
        if isinstance(v, str) and v.strip():
            input_genres.add(v)
    if not input_genres:
        return None

    mask = np.zeros(len(df), dtype=bool)
    for col in genre_cols:
        mask |= df[col].isin(input_genres).to_numpy()
    mask[input_idx] = False

    candidate_idx = np.flatnonzero(mask)
    if candidate_idx.size < 10:
        return None

    # Cosine distance vectorized over the (small) genre-matched subset.
    subset = X_scaled[candidate_idx]
    input_norm = float(np.linalg.norm(input_vec))
    if input_norm == 0:
        return None
    subset_norms = np.linalg.norm(subset, axis=1)
    safe_norms = np.where(subset_norms == 0, 1e-12, subset_norms)
    similarities = (subset @ input_vec) / (safe_norms * input_norm)
    distances = 1.0 - similarities

    top_k = np.argpartition(distances, 10)[:10]
    top_k = top_k[np.argsort(distances[top_k])]
    return [(int(candidate_idx[i]), float(distances[i])) for i in top_k]
