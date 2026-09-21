import { Badge } from "@/components/ui/badge";
import { TrackedCta } from "@/components/tracked-cta";
import {
  PRICING_HEADLINE,
  PRICING_SUBHEADLINE,
  PRICING_FREE,
  PRICING_PRO,
  PRICING_FOOTNOTE,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { Check } from "lucide-react";

function PlanCard({
  name,
  price,
  period,
  features,
  cta,
  ctaId,
  featured,
  badge,
}: {
  name: string;
  price: string;
  period: string;
  features: readonly string[];
  cta: string;
  ctaId: string;
  featured?: boolean;
  badge?: string;
}) {
  return (
    <article
      className={
        featured
          ? "reveal-on-scroll relative flex flex-col gap-6 rounded-lg border border-primary/50 bg-card p-6 shadow-lg shadow-primary/10"
          : "reveal-on-scroll flex flex-col gap-6 rounded-lg border bg-card/80 p-6"
      }
    >
      {badge ? (
        <Badge className="absolute -top-3 left-6 bg-secondary text-secondary-foreground">
          {badge}
        </Badge>
      ) : null}
      <div className="flex flex-col gap-1">
        <h3 className="font-heading text-xl text-white">{name}</h3>
        <p className="font-heading text-3xl text-primary-on-surface">{price}</p>
        <p className="text-sm text-white/50">{period}</p>
      </div>
      <ul className="flex flex-1 flex-col gap-3">
        {features.map((feature) => (
          <li key={feature} className="flex gap-2 text-sm text-white/75">
            <Check
              className="mt-0.5 size-4 shrink-0 text-secondary"
              aria-hidden
            />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      <TrackedCta
        href={TELEGRAM_BOT_URL}
        ctaId={ctaId}
        variant={featured ? "default" : "outline"}
        className={
          featured
            ? "btn-shine w-full justify-center"
            : "w-full justify-center border-white/20 bg-transparent text-white hover:bg-white/10"
        }
      >
        {cta}
      </TrackedCta>
    </article>
  );
}

export function PricingSection() {
  return (
    <section id="precos" className="px-4 py-20 sm:py-28">
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-10">
        <div className="flex max-w-2xl flex-col items-center gap-3 text-center">
          <h2 className="font-heading text-3xl leading-tight tracking-tight text-white sm:text-4xl">
            {PRICING_HEADLINE}
          </h2>
          <p className="text-lg leading-relaxed text-white/65">
            {PRICING_SUBHEADLINE}
          </p>
        </div>

        <div className="grid w-full gap-6 md:grid-cols-2 md:gap-8">
          <PlanCard
            name={PRICING_FREE.name}
            price={PRICING_FREE.price}
            period={PRICING_FREE.period}
            features={PRICING_FREE.features}
            cta={PRICING_FREE.cta}
            ctaId="pricing_free"
          />
          <PlanCard
            name={PRICING_PRO.name}
            price={PRICING_PRO.price}
            period={PRICING_PRO.period}
            features={PRICING_PRO.features}
            cta={PRICING_PRO.cta}
            ctaId="pricing_pro"
            featured
            badge={PRICING_PRO.badge}
          />
        </div>

        <p className="max-w-xl text-center text-sm text-white/45">
          {PRICING_FOOTNOTE}
        </p>
      </div>
    </section>
  );
}
