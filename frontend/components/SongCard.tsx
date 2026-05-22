"use client";

import type { Song } from "@/lib/api";
import { FeatureBars } from "./FeatureBars";
import { previewKey, usePreviewPlayer } from "./PreviewPlayer";

type Props = {
  song: Song;
  rank?: number;
  isInput?: boolean;
};

export function SongCard({ song, rank, isInput }: Props) {
  const similarityPct = Math.round(song.similarity * 100);
  const { statusFor, toggle } = usePreviewPlayer();
  const key = previewKey(song.name, song.artist);
  const status = statusFor(key);

  return (
    <div
      className={`group relative rounded-2xl border p-5 transition-all backdrop-blur-md ${
        isInput
          ? "border-melo/40 bg-gradient-to-br from-melo-dim/30 to-ink-700/60 shadow-lg shadow-melo/20"
          : "border-white/10 bg-ink-700/50 hover:border-melo/40 hover:bg-ink-600/60 hover:-translate-y-0.5"
      }`}
    >
      {rank !== undefined && (
        <div className="absolute -top-3 -left-3 h-8 w-8 rounded-full bg-melo text-ink-900 font-bold text-sm flex items-center justify-center shadow-md shadow-melo/30">
          {rank}
        </div>
      )}

      {isInput && (
        <div className="absolute -top-3 right-4 px-2 py-0.5 rounded-full bg-melo-neon text-ink-900 text-[10px] font-semibold tracking-wider uppercase">
          Your pick
        </div>
      )}

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-white truncate" title={song.name}>
            {song.name}
          </h3>
          <p
            className="text-sm text-white/60 truncate mt-0.5"
            title={song.artist}
          >
            {song.artist}
            {song.release_year ? (
              <span className="ml-2 text-white/30 font-mono text-[11px]">
                · {song.release_year}
              </span>
            ) : null}
          </p>
        </div>

        <div className="shrink-0 flex flex-col items-end gap-2">
          <PreviewButton
            status={status}
            onClick={() => toggle(key, song.name, song.artist)}
          />
          {!isInput && (
            <div className="text-right leading-tight">
              <div className="text-xl font-bold bg-gradient-to-r from-melo to-melo-neon bg-clip-text text-transparent">
                {similarityPct}%
              </div>
              <div className="text-[10px] uppercase tracking-wider text-white/40">
                match
              </div>
            </div>
          )}
        </div>
      </div>

      <FeatureBars features={song.features} />

      <a
        href={song.spotify_search_url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-flex items-center justify-center gap-2 w-full rounded-xl bg-[#1db954] hover:bg-[#1ed760] text-black font-semibold text-sm py-2 transition-colors"
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="h-4 w-4 fill-current"
        >
          <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.84-.179-.94-.6-.12-.421.18-.84.6-.94 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.282 1.121zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
        </svg>
        Open in Spotify
      </a>
    </div>
  );
}

function PreviewButton({
  status,
  onClick,
}: {
  status: "idle" | "loading" | "playing" | "no-preview";
  onClick: () => void;
}) {
  const isMissing = status === "no-preview";
  const isPlaying = status === "playing";
  const isLoading = status === "loading";

  const baseClasses =
    "h-10 w-10 rounded-full flex items-center justify-center transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-melo/50";
  const stateClasses = isMissing
    ? "bg-white/5 text-white/30 cursor-not-allowed shadow-none"
    : isPlaying
    ? "bg-gradient-to-br from-melo-neon to-melo text-ink-900 shadow-melo/40 scale-105"
    : "bg-gradient-to-br from-melo to-melo-dim text-white hover:scale-105 shadow-melo/30";

  return (
    <button
      type="button"
      onClick={isMissing ? undefined : onClick}
      disabled={isMissing}
      aria-label={
        isMissing
          ? "No preview available"
          : isPlaying
          ? "Pause preview"
          : "Play 30-second preview"
      }
      title={
        isMissing
          ? "No preview available"
          : isPlaying
          ? "Pause preview"
          : "Play 30-second preview"
      }
      className={`${baseClasses} ${stateClasses}`}
    >
      {isLoading ? (
        <span className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
      ) : isPlaying ? (
        <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden>
          <rect x="6" y="5" width="4" height="14" rx="1" />
          <rect x="14" y="5" width="4" height="14" rx="1" />
        </svg>
      ) : isMissing ? (
        <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden>
          <path d="M3 3l18 18-1.4 1.4-3-3A8 8 0 015 6.4L3.6 5 3 5.6 3 3zm9 5a4 4 0 00-3.6 5.6L12 17V13a1 1 0 011-1l4-1V8h-5z" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current ml-0.5" aria-hidden>
          <path d="M8 5v14l11-7z" />
        </svg>
      )}
    </button>
  );
}
