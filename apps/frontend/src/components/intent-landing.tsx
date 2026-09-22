import { TrackedCta } from "@/components/tracked-cta";
import { Footer } from "@/components/footer";
import { TELEGRAM_BOT_URL, SECTION_CTA_LABEL, HERO_CTA_HINT } from "@/content/page-content";
import type { SeoPage } from "@/content/seo-pages";
import { SITE_NAME } from "@/lib/site";
import Link from "next/link";

export function IntentLanding({ page }: { page: SeoPage }) {
  return (
    <div className="flex flex-1 flex-col">
      <main className="bg-surface">
        <section className="relative mx-auto flex max-w-3xl flex-col items-start gap-6 px-4 py-24 sm:py-32">
          <Link
            href="/"
            className="font-mono text-xs uppercase tracking-wider text-primary-on-surface hover:underline"
          >
            ← {SITE_NAME}
          </Link>
          <h1 className="font-heading text-4xl leading-tight tracking-tight text-white sm:text-5xl">
            {page.headline}
          </h1>
          <p className="text-lg leading-relaxed text-white/70">{page.body}</p>
          <div className="flex flex-col items-start gap-2">
            <TrackedCta
              href={TELEGRAM_BOT_URL}
              ctaId={`seo_${page.slug}`}
              className="btn-shine h-11 px-6 text-base"
            >
              {SECTION_CTA_LABEL}
            </TrackedCta>
            <p className="text-sm text-white/50">{HERO_CTA_HINT}</p>
          </div>
          <p className="text-sm text-white/40">
            Também monitoramos{" "}
            <Link href="/#precos" className="text-primary-on-surface hover:underline">
              Free e Radar Pro (Stars)
            </Link>
            .
          </p>
        </section>
      </main>
      <Footer />
    </div>
  );
}
