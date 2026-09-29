import { cn } from "@/lib/utils";

/**
 * Ornamento abstrato "dithered" no estilo do meuassessor.com — anéis de radar
 * montados de pontos (evocam a leitura visual do produto, radar de imóveis).
 * Puramente decorativo (aria-hidden) e responsivo.
 *
 * Pontos: cada círculo usa stroke-dasharray + stroke-linecap=round formando um
 * anel segmentado de "pixel dots", com raio e opacidade decrescentes.
 */
export function RadarOrnament({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 240"
      aria-hidden="true"
      className={cn(
        "pointer-events-none select-none text-white",
        className,
      )}
      fill="none"
    >
      {[120, 92, 64, 36].map((r, i) => (
        <circle
          key={r}
          cx="120"
          cy="120"
          r={r}
          stroke="currentColor"
          strokeWidth={r > 64 ? 1 : 1.5}
          strokeLinecap="round"
          strokeDasharray="0.5 9"
          opacity={0.5 - i * 0.1}
        />
      ))}
      {/* varredura de radar */}
      <path
        d="M120 120 L120 30 A90 90 0 0 1 197 63"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.8"
      />
      <circle cx="120" cy="120" r="3" fill="currentColor" opacity="0.9" />
      <circle cx="163" cy="77" r="2.5" fill="currentColor" opacity="0.55" />
      <circle cx="82" cy="150" r="2" fill="currentColor" opacity="0.4" />
    </svg>
  );
}