import {
  HOW_IT_WORKS_SOLUTION,
  HOW_IT_WORKS_HEADLINE,
  STEP_1_TITLE,
  STEP_1_DESC,
  STEP_2_TITLE,
  STEP_2_DESC,
  STEP_3_TITLE,
  STEP_3_DESC,
  SECTION_CTA_LABEL,
  WHATSAPP_ASSISTANT_URL,
} from "@/content/page-content";
import { TrackedCta } from "@/components/tracked-cta";

const steps = [
  {
    number: "01",
    title: STEP_1_TITLE,
    description: STEP_1_DESC,
  },
  {
    number: "02",
    title: STEP_2_TITLE,
    description: STEP_2_DESC,
  },
  {
    number: "03",
    title: STEP_3_TITLE,
    description: STEP_3_DESC,
  },
];

export function HowItWorks() {
  return (
    <section
      id="como-funciona"
      className="border-t border-white/8 bg-[#0a0a0c] px-4 py-20 sm:py-28"
    >
      <div className="mx-auto flex w-full max-w-4xl flex-col items-center gap-12">
        <div className="flex max-w-2xl flex-col items-center gap-4 text-center">
          <p className="font-heading text-sm font-medium uppercase tracking-[0.3em] text-primary-on-surface">
            Como funciona
          </p>
          <h2 className="font-heading text-3xl font-medium leading-tight tracking-tight text-white sm:text-4xl">
            {HOW_IT_WORKS_HEADLINE}
          </h2>
          <p className="text-lg leading-relaxed text-white/55">
            {HOW_IT_WORKS_SOLUTION}
          </p>
        </div>

        <div className="grid w-full gap-5 sm:grid-cols-3">
          {steps.map((step) => (
            <div
              key={step.number}
              className="reveal-on-scroll flex flex-col gap-3 rounded-2xl border border-white/10 bg-card p-6 transition-colors hover:border-white/20"
            >
              <span className="font-mono text-sm tracking-widest text-primary-on-surface">
                {step.number}
              </span>
              <h3 className="font-heading text-lg font-medium text-white">
                {step.title}
              </h3>
              <p className="text-sm leading-relaxed text-white/55">
                {step.description}
              </p>
            </div>
          ))}
        </div>

        <TrackedCta
          href={WHATSAPP_ASSISTANT_URL}
          ctaId="how_it_works"
          variant="pill"
        >
          {SECTION_CTA_LABEL}
        </TrackedCta>
      </div>
    </section>
  );
}