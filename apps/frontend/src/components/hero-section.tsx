import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import {
  HERO_HEADLINE,
  HERO_SUBHEADLINE,
  HERO_BADGE_TEXT,
  HERO_CTA_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";

export function HeroSection() {
  return (
    <section className="relative flex flex-col items-center justify-center overflow-hidden px-4 py-24 sm:py-32">
      {/* Fundo decorativo: grade + glow (não interativo) */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="bg-grid-fade absolute inset-0" />
        <div className="absolute left-1/2 top-1/2 h-[360px] w-[min(720px,100vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/15 blur-[120px]" />
      </div>

      <div className="relative z-10 flex w-full max-w-3xl flex-col items-center gap-6 text-center">
        <Badge
          variant="outline"
          className="border-primary/30 bg-primary/5 text-primary-on-surface font-mono text-xs uppercase tracking-wider animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
        >
          <span className="relative flex size-2" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-secondary opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-secondary" />
          </span>
          {HERO_BADGE_TEXT}
        </Badge>

        <h1 className="font-heading text-4xl leading-tight tracking-tight text-white animate-in fade-in slide-in-from-bottom-3 fill-mode-both duration-500 delay-100 sm:text-5xl md:text-6xl">
          {HERO_HEADLINE}
        </h1>

        <p className="max-w-xl text-lg leading-relaxed text-white/70 animate-in fade-in slide-in-from-bottom-3 fill-mode-both duration-500 delay-200 sm:text-xl">
          {HERO_SUBHEADLINE}
        </p>

        <a
          href={TELEGRAM_BOT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            buttonVariants({ variant: "default", size: "lg" }),
            "btn-shine mt-2 h-11 px-6 text-base animate-in fade-in slide-in-from-bottom-3 fill-mode-both duration-500 delay-300"
          )}
        >
          <Send className="size-4" data-icon="inline-start" />
          {HERO_CTA_LABEL}
        </a>
      </div>
    </section>
  );
}