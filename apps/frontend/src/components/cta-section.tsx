import {
  CTA_HEADLINE,
  CTA_SUBHEADLINE,
  CTA_BUTTON_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { TrackedCta } from "@/components/tracked-cta";

export function CTASection() {
  return (
    <section className="flex flex-col items-center justify-center bg-primary px-4 py-24 sm:py-32">
      <div className="reveal-on-scroll mx-auto flex w-full max-w-2xl flex-col items-center gap-6 text-center">
        <h2 className="font-heading text-3xl leading-tight tracking-tight text-primary-foreground sm:text-4xl">
          {CTA_HEADLINE}
        </h2>

        <p className="max-w-lg text-lg leading-relaxed text-primary-foreground/90">
          {CTA_SUBHEADLINE}
        </p>

        <TrackedCta
          href={TELEGRAM_BOT_URL}
          ctaId="final_cta"
          className="mt-2 h-11 px-6 text-base bg-white text-primary hover:bg-white/90"
        >
          {CTA_BUTTON_LABEL}
        </TrackedCta>
      </div>
    </section>
  );
}
