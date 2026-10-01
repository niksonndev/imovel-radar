import { AssistantDemo } from "@/components/landing/AssistantDemo";
import { RadarOrnament } from "@/components/landing/radar-ornament";
import { TrackedCta } from "@/components/tracked-cta";
import {
  HERO_HEADLINE,
  HERO_HEADLINE_LINE2,
  HERO_SUBHEADLINE,
  HERO_CTA_LABEL,
  HERO_CTA_HINT,
  WHATSAPP_ASSISTANT_URL,
} from "@/content/page-content";
import { SITE_NAME } from "@/lib/site";

export function HeroSection() {
  return (
    <section className="relative overflow-hidden px-4 pb-16 pt-10 sm:pb-24 sm:pt-16 lg:pt-20">
      {/* Fundo: glows suaves + textura pontilhada — sem a grade do layout antigo. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="dot-grid absolute inset-0 opacity-40" />
        <div className="absolute left-1/2 top-0 h-80 w-[min(720px,100vw)] -translate-x-1/2 -translate-y-1/3 rounded-full bg-primary/15 blur-[140px]" />
        <div className="absolute bottom-0 left-1/4 h-64 w-64 -translate-x-1/2 rounded-full bg-secondary/10 blur-[120px]" />
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-4xl flex-col items-center gap-6 text-center">
              <p className="font-heading text-sm font-medium uppercase tracking-[0.3em] text-primary-on-surface">
                {SITE_NAME}
              </p>

              <h1 className="font-heading text-4xl font-medium leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-6xl">
                {HERO_HEADLINE}
                <span className="mt-1 block font-light text-white/55">
                  {HERO_HEADLINE_LINE2}
                </span>
              </h1>

              <p className="max-w-2xl text-lg leading-relaxed text-white/60 sm:text-xl">
                {HERO_SUBHEADLINE}
              </p>

              <TrackedCta
                href={WHATSAPP_ASSISTANT_URL}
                ctaId="hero"
                variant="pill"
                size="cta"
              >
                {HERO_CTA_LABEL}
              </TrackedCta>
              <p className="-mt-3 text-sm text-white/55">{HERO_CTA_HINT}</p>

              {/* Mockup centralizado, emoldurado pelos anéis dithered nas laterais. */}
              <div className="relative mt-1 w-full max-w-md">
          <RadarOrnament className="absolute -left-24 top-1/2 hidden w-52 -translate-y-1/2 opacity-60 lg:block lg:-left-40" />
          <RadarOrnament className="absolute -right-24 top-1/2 hidden w-52 -translate-y-1/2 rotate-180 opacity-60 lg:block lg:-right-40" />
          <div className="animate-in fade-in slide-in-from-bottom-4 fill-mode-both duration-700 delay-150">
            <AssistantDemo />
          </div>
        </div>
      </div>
    </section>
  );
}