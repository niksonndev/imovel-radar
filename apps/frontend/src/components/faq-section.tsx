import { FAQ_HEADLINE, FAQ_ITEMS } from "@/content/page-content";

export function FaqSection() {
  return (
    <section className="px-4 py-20 sm:py-28">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-10">
        <h2 className="text-center font-heading text-3xl leading-tight tracking-tight text-white sm:text-4xl">
          {FAQ_HEADLINE}
        </h2>

        <div className="flex flex-col divide-y divide-white/10 border-y border-white/10">
          {FAQ_ITEMS.map((item) => (
            <details
              key={item.question}
              className="group reveal-on-scroll py-4"
            >
              <summary className="cursor-pointer list-none font-sans text-base font-semibold leading-6 text-white marker:content-none [&::-webkit-details-marker]:hidden sm:text-lg sm:leading-7">
                <span className="flex items-start justify-between gap-4">
                  {item.question}
                  <span
                    aria-hidden="true"
                    className="mt-1 shrink-0 font-mono text-sm text-white/40 transition-transform group-open:rotate-45"
                  >
                    +
                  </span>
                </span>
              </summary>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-white/65 sm:text-base">
                {item.answer}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
