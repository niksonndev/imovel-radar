import {
  HOW_IT_WORKS_HEADLINE,
  STEP_1_TITLE,
  STEP_1_DESC,
  STEP_2_TITLE,
  STEP_2_DESC,
  STEP_3_TITLE,
  STEP_3_DESC,
  SECTION_CTA_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const steps = [
  {
    number: 1,
    title: STEP_1_TITLE,
    description: STEP_1_DESC,
  },
  {
    number: 2,
    title: STEP_2_TITLE,
    description: STEP_2_DESC,
  },
  {
    number: 3,
    title: STEP_3_TITLE,
    description: STEP_3_DESC,
  },
];

export function HowItWorks() {
  return (
    <section className="px-4 py-20 sm:py-28">
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center gap-12">
        <h2 className="font-heading text-3xl leading-tight tracking-tight text-white sm:text-4xl">
          {HOW_IT_WORKS_HEADLINE}
        </h2>

        <div className="flex w-full flex-col gap-8">
          {steps.map((step, index) => (
            <div key={step.number} className="flex gap-5">
              {/* Number indicator */}
              <div className="flex flex-col items-center">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary font-mono text-sm font-bold text-primary-foreground">
                  {step.number}
                </span>
                {index < steps.length - 1 && (
                  <div className="draw-line mt-1 w-px flex-1 bg-white/20" />
                )}
              </div>

              {/* Step content */}
              <div className="reveal-on-scroll flex flex-col gap-1 pb-8">
                <h3 className="font-heading text-lg text-white">
                  {step.title}
                </h3>
                <p className="text-sm leading-relaxed text-white/60">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        <a
          href={TELEGRAM_BOT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(buttonVariants({ variant: "default", size: "lg" }), "btn-shine")}
        >
          {SECTION_CTA_LABEL}
        </a>
      </div>
    </section>
  );
}