type Props = {
  features: Record<string, number>;
};

const BARS: { key: string; label: string; max: number; color: string }[] = [
  { key: "danceability", label: "Dance", max: 1, color: "bg-melo" },
  { key: "energy", label: "Energy", max: 1, color: "bg-melo-neon" },
  { key: "valence", label: "Mood", max: 1, color: "bg-melo-pink" },
  { key: "tempo", label: "Tempo", max: 200, color: "bg-melo-glow" },
];

export function FeatureBars({ features }: Props) {
  return (
    <div className="mt-3 space-y-1.5">
      {BARS.map(({ key, label, max, color }) => {
        const raw = features[key] ?? 0;
        const pct = Math.max(0, Math.min(100, (raw / max) * 100));
        const display =
          key === "tempo" ? `${Math.round(raw)} bpm` : raw.toFixed(2);
        return (
          <div key={key} className="text-[10px] uppercase tracking-wider">
            <div className="flex justify-between text-white/50">
              <span>{label}</span>
              <span className="font-mono text-white/70">{display}</span>
            </div>
            <div className="mt-0.5 h-1.5 rounded-full bg-white/5 overflow-hidden">
              <div
                className={`h-full ${color} rounded-full transition-all duration-500`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
