"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type PreviewStatus = "idle" | "loading" | "playing" | "no-preview";

type Ctx = {
  statusFor: (key: string) => PreviewStatus;
  toggle: (key: string, name: string, artist: string) => Promise<void>;
  stop: () => void;
};

const PreviewCtx = createContext<Ctx | null>(null);

const ITUNES_ENDPOINT = "https://itunes.apple.com/search";

function cacheKey(name: string, artist: string) {
  return `${name.toLowerCase()}|${artist.toLowerCase()}`;
}

async function lookupPreviewUrl(name: string, artist: string): Promise<string | null> {
  const term = encodeURIComponent(`${name} ${artist}`.trim());
  const url = `${ITUNES_ENDPOINT}?term=${term}&entity=song&limit=1`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = (await res.json()) as { results?: { previewUrl?: string }[] };
    return data.results?.[0]?.previewUrl ?? null;
  } catch {
    return null;
  }
}

export function PreviewPlayerProvider({ children }: { children: ReactNode }) {
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [missingKeys, setMissingKeys] = useState<Set<string>>(new Set());
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlCacheRef = useRef<Map<string, string | null>>(new Map());

  // Lazily construct one shared <audio> element on the client.
  useEffect(() => {
    if (typeof window === "undefined" || audioRef.current) return;
    const audio = new Audio();
    audio.preload = "none";
    audio.addEventListener("ended", () => setActiveKey(null));
    audio.addEventListener("error", () => setActiveKey(null));
    audioRef.current = audio;
    return () => {
      audio.pause();
      audio.src = "";
      audioRef.current = null;
    };
  }, []);

  const stop = useCallback(() => {
    audioRef.current?.pause();
    setActiveKey(null);
    setLoadingKey(null);
  }, []);

  const toggle = useCallback(
    async (key: string, name: string, artist: string) => {
      if (activeKey === key) {
        stop();
        return;
      }
      audioRef.current?.pause();
      setActiveKey(null);

      let url = urlCacheRef.current.get(key);
      if (url === undefined) {
        setLoadingKey(key);
        url = await lookupPreviewUrl(name, artist);
        urlCacheRef.current.set(key, url);
        setLoadingKey((curr) => (curr === key ? null : curr));
      }

      if (!url) {
        setMissingKeys((prev) => {
          if (prev.has(key)) return prev;
          const next = new Set(prev);
          next.add(key);
          return next;
        });
        return;
      }

      const audio = audioRef.current;
      if (!audio) return;
      audio.src = url;
      try {
        await audio.play();
        setActiveKey(key);
      } catch {
        setActiveKey(null);
      }
    },
    [activeKey, stop],
  );

  const statusFor = useCallback(
    (key: string): PreviewStatus => {
      if (loadingKey === key) return "loading";
      if (activeKey === key) return "playing";
      if (missingKeys.has(key)) return "no-preview";
      return "idle";
    },
    [activeKey, loadingKey, missingKeys],
  );

  return (
    <PreviewCtx.Provider value={{ statusFor, toggle, stop }}>
      {children}
    </PreviewCtx.Provider>
  );
}

export function usePreviewPlayer() {
  const ctx = useContext(PreviewCtx);
  if (!ctx) throw new Error("usePreviewPlayer must be inside <PreviewPlayerProvider>");
  return ctx;
}

export function previewKey(name: string, artist: string) {
  return cacheKey(name, artist);
}
