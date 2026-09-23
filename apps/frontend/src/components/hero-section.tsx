import { TrackedCta } from "@/components/tracked-cta";
import { TelegramAlertMock } from "@/components/telegram-alert-mock";
import {
  HERO_HEADLINE,
  HERO_HEADLINE_LINE2,
  HERO_SUBHEADLINE,
  HERO_CTA_LABEL,
  HERO_CTA_HINT,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { SITE_NAME } from "@/lib/site";

export function HeroSection() {
  return (
    <section className="relative overflow-hidden px-4 py-16 sm:py-24 lg:py-28">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="bg-grid-fade absolute inset-0" />
        <div className="absolute left-1/2 top-1/3 h-[360px] w-[min(720px,100vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/15 blur-[120px] lg:left-[30%]" />
      </div>

      <div className="relative z-10 mx-auto grid w-full max-w-6xl items-center gap-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-16">
        <div className="flex flex-col items-center gap-6 text-center lg:items-start lg:text-left">
          <p className="font-heading text-sm uppercase tracking-[0.2em] text-primary-on-surface animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500">
            {SITE_NAME}
          </p>

          <h1 className="font-heading text-4xl leading-tight tracking-tight text-white animate-in fade-in slide-in-from-bottom-3 fill-mode-both duration-500 delay-100 sm:text-5xl md:text-6xl">
            {HERO_HEADLINE}
            <span className="mt-1 block text-primary-on-surface">{HERO_HEADLINE_LINE2}</span>
          </h1>

          <p className="max-w-xl text-lg leading-relaxed text-white/70 animate-in fade-in slide-in-from-bottom-3 fill-mode-both duration-500 delay-200 sm:text-xl">
            {HERO_SUBHEADLINE}
          </p>

          <div className="flex flex-col items-center gap-2 animate-in fade-in slide-in-from-bottom-3 fill-mode-both duration-500 delay-300 lg:items-start">
            <TrackedCta
              href={TELEGRAM_BOT_URL}
              ctaId="hero"
              className="btn-shine mt-2"
            >
              {HERO_CTA_LABEL}
            </TrackedCta>
            <p className="text-sm text-white/50">{HERO_CTA_HINT}</p>
          </div>
        </div>

        <div className="animate-in fade-in slide-in-from-bottom-4 fill-mode-both duration-700 delay-200">
          <TelegramAlertMock />
        </div>
      </div>
    </section>
  );
}
