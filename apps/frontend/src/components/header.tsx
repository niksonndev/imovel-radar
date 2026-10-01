import Link from "next/link";
import { Radar } from "lucide-react";
import { TrackedCta } from "@/components/tracked-cta";
import {
  SECTION_CTA_LABEL,
  WHATSAPP_ASSISTANT_URL,
} from "@/content/page-content";
import { SITE_NAME } from "@/lib/site";

const NAV = [
  { href: "/#como-funciona", label: "Como funciona" },
  { href: "/#precos", label: "Preços" },
  { href: "/mercado", label: "Mercado" },
  { href: "/imoveis", label: "Imóveis" },
] as const;

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-[#050505]/70 bg-surface/70 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4">
        <Link
          href="/"
          aria-label={`${SITE_NAME} — início`}
          className="flex items-center gap-2 text-white"
        >
          <span className="flex size-8 items-center justify-center rounded-full bg-primary">
            <Radar className="size-4.5 text-white" aria-hidden />
          </span>
          <span className="font-heading text-base tracking-tight">
            {SITE_NAME}
          </span>
        </Link>

        <nav
          aria-label="Navegação principal"
          className="hidden items-center gap-6 md:flex"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm text-white/65 transition-colors hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <TrackedCta
          href={WHATSAPP_ASSISTANT_URL}
          ctaId="header"
          variant="pill"
          size="sm"
        >
          {SECTION_CTA_LABEL}
        </TrackedCta>
      </div>
    </header>
  );
}