# Melo AI

A song recommendation engine that finds tracks sonically similar to ones you love, constrained to the same genre family. Built as a Next.js 14 frontend over a FastAPI + scikit-learn backend running KNN against ~268k Spotify tracks.

Search a song, get ten musically related results — each with a 30-second audio preview, audio-feature bars, and a one-click jump to Spotify.

---

## How it works

1. **Type a song.** Autocomplete suggests tracks from the library ranked by real Spotify popularity, so the obvious match comes up first.
2. **Look up genres.** The backend reads the input's three genres (`genre_1/2/3`) from the dataset.
3. **Filter by genre family.** Every song that shares at least one genre with the input is gathered as a candidate.
4. **Rank by audio similarity.** Within that subset, the top 10 closest by cosine distance over 11 audio features (`danceability, energy, key, loudness, mode, speechiness, acousticness, instrumentalness, liveness, valence, tempo`) are returned.
5. **Preview & open.** Each card streams a 30-second clip from the iTunes Search API on demand, or links straight to the track on Spotify.

Pure audio-feature KNN was the original approach but kept crossing genre boundaries (a pop song would surface a tempo-matched classical piano piece). Pre-filtering by genre, then ranking by audio similarity inside that pool, gives recommendations that feel right — the prototype `test/prototype.ipynb` used the same insight.

---

## Features

- Typeahead song search across all 268k tracks, popularity-ranked
- Genre-constrained KNN recommendations (cosine distance on 11 audio features)
- 30-second previews via the iTunes Search API — no Spotify auth required
- Per-card audio feature bars (`Dance / Energy / Mood / Tempo`)
- "Open in Spotify" button on every result
- Dark, music-themed Tailwind UI with keyboard nav on the typeahead

---

## Tech stack

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Backend:** FastAPI, Uvicorn
- **ML:** pandas + scikit-learn (`NearestNeighbors`, cosine metric)
- **Hosting:** Vercel (frontend) + Render (backend)
- **Previews:** iTunes Search API (public, no auth)
- **Data:** 268k tracks with Spotify audio features, popularity, year, and up to 3 genres per track

---

## Run locally

Requires Python 3.11+ and Node 18+.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

First boot reads `data/mainDB.csv` (~44 MB), fits the KNN model, and serves the API at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
cp .env.local.example .env.local      # points NEXT_PUBLIC_API_URL at localhost:8000
npm install
npm run dev
```

Open `http://localhost:3000` and search a song. Try **Blinding Lights** by The Weeknd or **SICKO MODE** by Travis Scott.

---

## API

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| `GET` | `/api/health` | — | `{status, dataset_size, source}` |
| `GET` | `/api/search` | `?q=<text>&limit=<n>` | Top N popularity-ranked autocomplete matches |
| `POST` | `/api/recommend` | `{track_name, artist_name?}` | Input song + 10 genre-matched recommendations with audio features and release year |

---

## Project structure

```
backend/
  main.py              FastAPI app, KNN model, /api/health, /api/search, /api/recommend
  requirements.txt
data/
  mainDB.csv           268k tracks (name, artist, popularity, year, 11 features, 3 genres)
  genreDB.csv          Genre lookup table
  sorted_artist_ids.csv
data_code/
  ArtistIdToMainDb.ipynb   Original Spotipy-based ingestion pipeline
  build_500k.py            Optional Kaggle 1.2M re-build (not used by deployed backend)
frontend/
  app/
    page.tsx           Search + results + PreviewPlayerProvider
    layout.tsx
    globals.css
  components/
    SongCard.tsx
    SongSearchInput.tsx  Debounced typeahead with keyboard nav
    FeatureBars.tsx
    PreviewPlayer.tsx    Single-audio-element context, iTunes lookup cache
  lib/
    api.ts
test/
  prototype.ipynb      The original notebook this app is based on
render.yaml            Render blueprint (Python web service, free tier)
```

---

## Deployment

The repo deploys as a split frontend/backend:

- **Render** runs `backend/` as a Python web service. Free tier has 512 MB RAM, which is enough for the 268k dataset (~380 MB resident). `render.yaml` at the repo root configures it — point Render at your fork via *New → Blueprint* and it picks up the rest.
- **Vercel** runs `frontend/`. In Vercel's import flow, set the project root to `frontend/` and add an environment variable `NEXT_PUBLIC_API_URL` pointing at the Render service URL.

Both auto-redeploy on every push to `main`.

---

## Notes on the dataset

The shipped `data/mainDB.csv` is a curated set of ~268k tracks scraped via Spotipy and joined to artist-level genres (see `data_code/ArtistIdToMainDb.ipynb`). It carries Spotify's `popularity` field, which is what makes the typeahead useful — without it, autocomplete can't tell the original "Blinding Lights" from twenty cover versions.

`data_code/build_500k.py` is an alternative pipeline that pulls the 1.2M-track Kaggle Spotify dataset and downsamples to 500k. It's kept for experimentation but isn't the default because (a) that source has no popularity column, (b) its long tail introduces noisy outliers (live recordings, voice memos, ambient interludes), and (c) at 500k rows the backend pushes Render's 512 MB free tier ceiling.

> Spotify locked down the `audio-features` endpoint for new API apps in late 2024. The original ingestion notebook is preserved as a historical reference but won't run end-to-end with fresh credentials.

---

## Acknowledgements

Audio features and popularity come from Spotify. Previews come from the iTunes Search API. The genre-aware KNN approach is borrowed from the original `test/prototype.ipynb` that this app builds on.
