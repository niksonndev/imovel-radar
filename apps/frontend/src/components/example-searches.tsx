import { TrackedCta } from "@/components/tracked-cta";
import {
  EXAMPLE_SEARCHES_HEADLINE,
  EXAMPLE_SEARCHES_SUBHEADLINE,
  EXAMPLE_SEARCHES,
  EXAMPLE_SEARCHES_CTA,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";

export function ExampleSearches() {
  return (
    <section className="px-4 py-16 sm:py-24">
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center gap-8 text-center">
        <div className="flex flex-col gap-3">
          <h2 className="font-heading text-3xl leading-tight tracking-tight text-white sm:text-4xl">
            {EXAMPLE_SEARCHES_HEADLINE}
          </h2>
          <p className="text-lg leading-relaxed text-white/65">
            {EXAMPLE_SEARCHES_SUBHEADLINE}
          </p>
        </div>

        <ul className="flex w-full flex-col gap-3 sm:gap-4">
          {EXAMPLE_SEARCHES.map((search) => (
            <li
              key={search}
              className="reveal-on-scroll border-b border-white/10 px-1 py-3 text-left font-mono text-sm text-white/80 sm:text-center sm:text-base"
            >
              {search}
            </li>
          ))}
        </ul>

        <TrackedCta
          href={TELEGRAM_BOT_URL}
          ctaId="example_searches"
          className="btn-shine"
        >
          {EXAMPLE_SEARCHES_CTA}
        </TrackedCta>
      </div>
    </section>
  );
}
