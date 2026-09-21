import {
  MARQUEE_LABEL,
  MONITORED_NEIGHBORHOODS,
} from "@/content/page-content";

export function NeighborhoodsMarquee() {
  // Lista duplicada para o loop seamless do marquee (translateX(-50%)).
  const items = [...MONITORED_NEIGHBORHOODS, ...MONITORED_NEIGHBORHOODS];

  return (
    <section
      aria-label={MARQUEE_LABEL}
      className="overflow-hidden border-y border-border/60 bg-card/40 py-4"
    >
      <div className="animate-marquee flex w-max items-center">
        {items.map((neighborhood, index) => (
          <span
            key={`${neighborhood}-${index}`}
            aria-hidden={index >= MONITORED_NEIGHBORHOODS.length || undefined}
            className="flex items-center gap-10 pr-10 font-mono text-sm uppercase tracking-widest text-white/50"
          >
            {neighborhood}
            <span aria-hidden="true" className="text-primary">
              •
            </span>
          </span>
        ))}
      </div>
    </section>
  );
}