"use client";

import { useState, FormEvent } from "react";
import { fetchRecommendations, type RecommendResponse } from "@/lib/api";
import { SongCard } from "@/components/SongCard";
import { SongSearchInput } from "@/components/SongSearchInput";
import {
  PreviewPlayerProvider,
  usePreviewPlayer,
} from "@/components/PreviewPlayer";

export default function Home() {
  return (
    <PreviewPlayerProvider>
      <HomeInner />
    </PreviewPlayerProvider>
  );
}

const ERA_OPTIONS: { label: string; value: number; hint: string }[] = [
  { label: "Any era", value: 0, hint: "No year filter" },
  { label: "Within 5 years", value: 5, hint: "Same musical era" },
  { label: "Within 2 years", value: 2, hint: "Tight contemporaries" },
];

function HomeInner() {
  const [trackName, setTrackName] = useState("");
  const [artistName, setArtistName] = useState("");
  const [maxYearDiff, setMaxYearDiff] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<RecommendResponse | null>(null);
  const { stop } = usePreviewPlayer();

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!trackName.trim()) return;
    stop();
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const res = await fetchRecommendations(
        trackName.trim(),
        artistName.trim(),
        maxYearDiff,
      );
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-10 sm:py-16">
      <div className="mx-auto max-w-6xl">
        <header className="text-center mb-10 sm:mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-xs uppercase tracking-widest text-white/60 mb-5">
            <span className="h-1.5 w-1.5 rounded-full bg-melo-neon animate-pulse-slow" />
            KNN over 268k tracks
          </div>
          <h1 className="text-5xl sm:text-7xl font-bold tracking-tight">
            <span className="bg-gradient-to-r from-melo-glow via-melo to-melo-neon bg-clip-text text-transparent">
              Melo
            </span>
            <span className="text-white"> AI</span>
          </h1>
          <p className="mt-4 text-white/60 text-base sm:text-lg max-w-xl mx-auto">
            Find songs that sound like the ones you love. Type a track, get ten
            sonically similar tracks based on Spotify audio features.
          </p>
        </header>

        <form
          onSubmit={onSubmit}
          className="mx-auto max-w-3xl rounded-2xl border border-white/10 bg-ink-700/40 backdrop-blur-md p-4 sm:p-6 shadow-xl shadow-black/40"
        >
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3">
            <SongSearchInput
              value={trackName}
              onChange={setTrackName}
              onPick={(name, artist) => {
                setTrackName(name);
                setArtistName(artist);
              }}
              placeholder="Song name (try typing 'blind…')"
            />
            <input
              type="text"
              value={artistName}
              onChange={(e) => setArtistName(e.target.value)}
              placeholder="Artist (optional)"
              className="rounded-xl bg-ink-800/80 border border-white/10 px-4 py-3 text-white placeholder:text-white/30 focus:outline-none focus:border-melo focus:ring-2 focus:ring-melo/30 transition"
            />
            <button
              type="submit"
              disabled={loading || !trackName.trim()}
              className="rounded-xl bg-gradient-to-r from-melo to-melo-neon text-ink-900 font-semibold px-6 py-3 hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg shadow-melo/30"
            >
              {loading ? "Searching…" : "Find Similar Songs"}
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.25em] text-white/40 mr-2">
              Era
            </span>
            {ERA_OPTIONS.map((opt) => {
              const active = opt.value === maxYearDiff;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setMaxYearDiff(opt.value)}
                  title={opt.hint}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    active
                      ? "border-melo-neon/60 bg-melo-neon/15 text-white"
                      : "border-white/10 bg-white/5 text-white/60 hover:border-white/20 hover:text-white/80"
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>

          <p className="text-xs text-white/40 mt-3">
            Start typing a song — only tracks in the library will appear. Tap
            the ▶ on any card for a 30-second preview.
          </p>
        </form>

        <section className="mt-10">
          {loading && <LoadingSkeleton />}

          {error && (
            <div className="mx-auto max-w-3xl rounded-2xl border border-melo-pink/40 bg-melo-pink/10 text-melo-pink p-4 text-center">
              {error}
            </div>
          )}

          {data && !loading && (
            <>
              <div className="mx-auto max-w-3xl mb-8">
                <SongCard song={data.input_song} isInput />
              </div>

              <h2 className="text-center text-xs uppercase tracking-[0.3em] text-white/40 mb-6">
                Sonically similar
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {data.recommendations.map((song, i) => (
                  <SongCard
                    key={`${song.name}-${song.artist}-${i}`}
                    song={song}
                    rank={i + 1}
                  />
                ))}
              </div>
            </>
          )}

          {!data && !loading && !error && (
            <div className="text-center text-white/40 mt-16">
              <div className="text-6xl mb-3">♪</div>
              <p>Search a song to get started.</p>
            </div>
          )}
        </section>

        <footer className="mt-20 text-center text-xs text-white/30">
          Built with FastAPI + scikit-learn KNN · Next.js + Tailwind · Previews
          from iTunes
        </footer>
      </div>
    </main>
  );
}

function LoadingSkeleton() {
  return (
    <>
      <div className="mx-auto max-w-3xl mb-8">
        <div className="h-44 rounded-2xl border border-white/10 bg-ink-700/40 animate-pulse" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            className="h-64 rounded-2xl border border-white/10 bg-ink-700/40 animate-pulse"
            style={{ animationDelay: `${i * 60}ms` }}
          />
        ))}
      </div>
    </>
  );
}
