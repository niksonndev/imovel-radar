import {
  FOOTER_TELEGRAM_LABEL,
  FOOTER_LEGAL,
  FOOTER_DISCLAIMER,
  FOOTER_PRIVACY,
  FOOTER_CONTACT_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { TrackedCta } from "@/components/tracked-cta";
import { SEO_PAGES } from "@/content/seo-pages";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="flex flex-col items-center justify-center gap-6 bg-surface px-4 py-12">
      <nav
        aria-label="Links do rodapé"
        className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2"
      >
        <TrackedCta
          href={TELEGRAM_BOT_URL}
          ctaId="footer_bot"
          variant="ghost"
          size="sm"
          showIcon={false}
          className="text-white/70 hover:bg-white/10 hover:text-white"
        >
          {FOOTER_TELEGRAM_LABEL}
        </TrackedCta>
        <TrackedCta
          href={TELEGRAM_BOT_URL}
          ctaId="footer_contact"
          variant="ghost"
          size="sm"
          showIcon={false}
          className="text-white/70 hover:bg-white/10 hover:text-white"
        >
          {FOOTER_CONTACT_LABEL}
        </TrackedCta>
        <Link
          href="/#precos"
          className="text-sm text-white/70 transition-colors hover:text-white"
        >
          Preços
        </Link>
        <Link
          href="/mercado"
          className="text-sm text-white/70 transition-colors hover:text-white"
        >
          Mercado
        </Link>
        <Link
          href="/imoveis"
          className="text-sm text-white/70 transition-colors hover:text-white"
        >
          Imóveis por cidade
        </Link>
        {SEO_PAGES.map((page) => (
          <Link
            key={page.slug}
            href={page.path}
            className="text-sm text-white/70 transition-colors hover:text-white"
          >
            {page.slug === "aluguel-maceio" ? "Aluguel Maceió" : "Comprar Maceió"}
          </Link>
        ))}
      </nav>

      <div className="flex max-w-xl flex-col gap-2 text-center">
        <p className="text-xs leading-relaxed text-white/45">
          {FOOTER_DISCLAIMER}
        </p>
        <p className="text-xs leading-relaxed text-white/45">{FOOTER_PRIVACY}</p>
      </div>

      <p className="font-mono text-xs tracking-wider text-white/40">
        {FOOTER_LEGAL}
      </p>
    </footer>
  );
}
