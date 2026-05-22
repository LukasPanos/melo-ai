"use client";

import { useEffect, useRef, useState } from "react";
import { searchSongs, type SearchHit } from "@/lib/api";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onPick: (name: string, artist: string) => void;
  placeholder?: string;
};

export function SongSearchInput({ value, onChange, onPick, placeholder }: Props) {
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const wrapRef = useRef<HTMLDivElement>(null);
  const justPickedRef = useRef(false);

  useEffect(() => {
    if (justPickedRef.current) {
      justPickedRef.current = false;
      return;
    }
    const q = value.trim();
    if (q.length < 2) {
      setHits([]);
      setOpen(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const res = await searchSongs(q, controller.signal);
        setHits(res.results);
        setActiveIdx(-1);
        setOpen(true);
      } catch (e) {
        if ((e as { name?: string }).name !== "AbortError") setHits([]);
      } finally {
        setLoading(false);
      }
    }, 150);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [value]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function pick(hit: SearchHit) {
    justPickedRef.current = true;
    onPick(hit.name, hit.artist);
    setOpen(false);
    setHits([]);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || hits.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => (i + 1) % hits.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => (i <= 0 ? hits.length - 1 : i - 1));
    } else if (e.key === "Enter" && activeIdx >= 0) {
      e.preventDefault();
      pick(hits[activeIdx]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={wrapRef} className="relative">
      <input
        type="text"
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => hits.length > 0 && setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        className="w-full rounded-xl bg-ink-800/80 border border-white/10 px-4 py-3 text-white placeholder:text-white/30 focus:outline-none focus:border-melo focus:ring-2 focus:ring-melo/30 transition"
      />
      {loading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 border-2 border-melo/40 border-t-melo rounded-full animate-spin" />
      )}
      {open && hits.length > 0 && (
        <ul
          role="listbox"
          className="absolute top-full left-0 right-0 mt-2 max-h-72 overflow-auto rounded-xl border border-white/10 bg-ink-800/95 backdrop-blur-md shadow-2xl shadow-black/60 z-20"
        >
          {hits.map((h, i) => (
            <li key={`${h.name}-${h.artist}-${i}`} role="option" aria-selected={i === activeIdx}>
              <button
                type="button"
                onMouseEnter={() => setActiveIdx(i)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(h);
                }}
                className={`w-full text-left px-4 py-2.5 flex items-center justify-between gap-3 transition-colors ${
                  i === activeIdx ? "bg-melo/15" : "hover:bg-white/5"
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-white truncate">{h.name}</div>
                  <div className="text-xs text-white/50 truncate">{h.artist}</div>
                </div>
                <span className="shrink-0 text-[10px] font-mono text-white/40 tabular-nums">
                  ♪ {h.popularity}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {open && !loading && value.trim().length >= 2 && hits.length === 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 rounded-xl border border-white/10 bg-ink-800/95 backdrop-blur-md px-4 py-3 text-sm text-white/50 z-20">
          No songs found in the library.
        </div>
      )}
    </div>
  );
}
