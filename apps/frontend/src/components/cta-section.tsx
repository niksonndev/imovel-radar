import {
  CTA_HEADLINE,
  CTA_SUBHEADLINE,
  CTA_BUTTON_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function CTASection() {
  return (
    <section className="flex flex-col items-center justify-center bg-primary px-4 py-24 sm:py-32">
      <div className="flex w-full max-w-2xl flex-col items-center gap-6 text-center">
        <h2 className="font-heading text-3xl leading-tight tracking-tight text-primary-foreground sm:text-4xl">
          {CTA_HEADLINE}
        </h2>

        <p className="max-w-lg text-lg leading-relaxed text-primary-foreground">
          {CTA_SUBHEADLINE}
        </p>

        <a
          href={TELEGRAM_BOT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            buttonVariants({ variant: "default", size: "lg" }),
            "mt-2 bg-white text-primary hover:bg-white/90"
          )}
        >
          {CTA_BUTTON_LABEL}
        </a>
      </div>
    </section>
  );
}