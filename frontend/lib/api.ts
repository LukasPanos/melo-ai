export type Song = {
  name: string;
  artist: string;
  spotify_search_url: string;
  similarity: number;
  features: Record<string, number>;
};

export type RecommendResponse = {
  input_song: Song;
  recommendations: Song[];
};

export type SearchHit = {
  name: string;
  artist: string;
  popularity: number;
};

export type SearchResponse = {
  results: SearchHit[];
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export async function fetchRecommendations(
  trackName: string,
  artistName: string,
): Promise<RecommendResponse> {
  const res = await fetch(`${API_URL}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_name: trackName, artist_name: artistName }),
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return res.json();
}

export async function searchSongs(
  query: string,
  signal?: AbortSignal,
  limit = 10,
): Promise<SearchResponse> {
  const url = `${API_URL}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`;
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Search failed (${res.status})`);
  return res.json();
}
