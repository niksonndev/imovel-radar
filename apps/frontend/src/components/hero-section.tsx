import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  HERO_HEADLINE,
  HERO_SUBHEADLINE,
  HERO_BADGE_TEXT,
  HERO_CTA_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";

export function HeroSection() {
  return (
    <section className="flex flex-col items-center justify-center px-4 py-24 sm:py-32">
      <div className="flex w-full max-w-3xl flex-col items-center gap-6 text-center">
        <Badge
          variant="outline"
          className="border-primary/30 text-primary-on-surface font-mono text-xs uppercase tracking-wider"
        >
          {HERO_BADGE_TEXT}
        </Badge>

        <h1 className="font-heading text-4xl leading-tight tracking-tight text-white sm:text-5xl md:text-6xl">
          {HERO_HEADLINE}
        </h1>

        <p className="max-w-xl text-lg leading-relaxed text-white/70 sm:text-xl">
          {HERO_SUBHEADLINE}
        </p>

        <a
          href={TELEGRAM_BOT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(buttonVariants({ variant: "default", size: "lg" }), "mt-2")}
        >
          {HERO_CTA_LABEL}
        </a>
      </div>
    </section>
  );
}