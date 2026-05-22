"""Melo AI — FastAPI backend exposing a KNN song-recommendation model."""
from __future__ import annotations

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

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "mainDB.csv"

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not DATA_PATH.exists():
        raise RuntimeError(f"Dataset not found at {DATA_PATH}")

    # Only load the columns we need — keeps memory under Render's 512 MB free tier.
    df = pd.read_csv(
        DATA_PATH,
        usecols=["song_name", "artist", "popularity", *FEATURE_COLS],
    )
    df = df.dropna(subset=FEATURE_COLS + ["song_name", "artist"]).reset_index(drop=True)
    df["song_name_lower"] = df["song_name"].astype(str).str.strip().str.lower()
    df["artist_lower"] = df["artist"].astype(str).str.strip().str.lower()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[FEATURE_COLS].astype(np.float32).to_numpy()).astype(np.float32)

    knn = NearestNeighbors(n_neighbors=11, metric="cosine", algorithm="brute")
    knn.fit(X_scaled)

    state["df"] = df
    state["X_scaled"] = X_scaled
    state["knn"] = knn
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


class RecommendResponse(BaseModel):
    input_song: Song
    recommendations: list[Song]


def _spotify_search_url(name: str, artist: str) -> str:
    q = urllib.parse.quote(f"{name} {artist}".strip())
    return f"https://open.spotify.com/search/{q}"


def _row_to_song(row: pd.Series, similarity: float) -> Song:
    return Song(
        name=str(row["song_name"]),
        artist=str(row["artist"]),
        spotify_search_url=_spotify_search_url(str(row["song_name"]), str(row["artist"])),
        similarity=round(float(similarity), 4),
        features={col: float(row[col]) for col in FEATURE_COLS},
    )


@app.get("/api/health")
def health() -> dict:
    df = state.get("df")
    return {
        "status": "ok",
        "dataset_size": int(0 if df is None else len(df)),
    }


@app.post("/api/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    df: pd.DataFrame = state["df"]
    X_scaled: np.ndarray = state["X_scaled"]
    knn: NearestNeighbors = state["knn"]

    name_q = req.track_name.strip().lower()
    artist_q = (req.artist_name or "").strip().lower()

    mask = df["song_name_lower"] == name_q
    if artist_q:
        mask = mask & (df["artist_lower"] == artist_q)
    matches = df.index[mask].to_numpy()

    if matches.size == 0:
        # Fall back to "contains" so minor punctuation/casing differences still hit.
        loose_mask = df["song_name_lower"].str.contains(name_q, regex=False, na=False)
        if artist_q:
            loose_mask = loose_mask & df["artist_lower"].str.contains(artist_q, regex=False, na=False)
        matches = df.index[loose_mask].to_numpy()

    if matches.size == 0:
        raise HTTPException(
            status_code=404,
            detail=f"'{req.track_name}' not found in the library. Try a different spelling.",
        )

    # If multiple matches, prefer the most popular one.
    if matches.size > 1 and "popularity" in df.columns:
        popularities = df.loc[matches, "popularity"].astype(float).to_numpy()
        idx = int(matches[int(np.argmax(popularities))])
    else:
        idx = int(matches[0])

    input_vec = X_scaled[idx].reshape(1, -1)
    distances, indices = knn.kneighbors(input_vec)

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
