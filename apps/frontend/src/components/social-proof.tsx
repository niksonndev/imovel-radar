import {
  SOCIAL_PROOF_HEADLINE,
  SOCIAL_PROOF_STATS,
  SOCIAL_PROOF_QUOTES,
} from "@/content/page-content";

export function SocialProof() {
  return (
    <section className="px-4 py-16 sm:py-20">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-12">
        <h2 className="text-center font-heading text-2xl leading-tight tracking-tight text-white sm:text-3xl">
          {SOCIAL_PROOF_HEADLINE}
        </h2>

        <dl className="grid gap-6 sm:grid-cols-3">
          {SOCIAL_PROOF_STATS.map((stat) => (
            <div
              key={stat.label}
              className="reveal-on-scroll flex flex-col items-center gap-1 text-center"
            >
              <dt className="font-heading text-3xl text-primary-on-surface sm:text-4xl">
                {stat.value}
              </dt>
              <dd className="max-w-[14rem] text-sm text-white/55">{stat.label}</dd>
            </div>
          ))}
        </dl>

        <div className="grid gap-6 md:grid-cols-2">
          {SOCIAL_PROOF_QUOTES.map((item) => (
            <blockquote
              key={item.attribution}
              className="reveal-on-scroll border-l-2 border-primary/50 pl-5"
            >
              <p className="text-base leading-relaxed text-white/80">
                “{item.quote}”
              </p>
              <footer className="mt-3 font-mono text-xs uppercase tracking-wider text-white/45">
                {item.attribution}
              </footer>
            </blockquote>
          ))}
        </div>
      </div>
    </section>
  );
}
