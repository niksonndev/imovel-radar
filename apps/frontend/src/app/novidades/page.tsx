import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight } from "lucide-react";

import { TrackedCta } from "@/components/tracked-cta";
import { WHATSAPP_ASSISTANT_URL } from "@/content/page-content";
import { SITE_NAME, SITE_URL } from "@/lib/site";

const title = `Novidades | ${SITE_NAME}`;
const description =
  "Comunicados e novidades sobre o André Assistente Imobiliário.";

export const metadata: Metadata = {
  title: { absolute: title },
  description,
  alternates: { canonical: "/novidades" },
  openGraph: {
    title,
    description,
    url: `${SITE_URL.replace(/\/$/, "")}/novidades`,
    locale: "pt_BR",
    type: "website",
  },
};

export default function NovidadesPage() {
  return (
    <main className="flex flex-1 flex-col bg-surface text-white">
      <header className="mx-auto flex w-full max-w-6xl items-center px-4 py-6">
        <Link
          href="/"
          className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-primary-on-surface hover:text-white"
        >
          <ArrowLeft aria-hidden="true" className="size-4" />
          {SITE_NAME}
        </Link>
      </header>
      <section className="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-4 pb-20 pt-10">
        <div className="max-w-3xl">
          <p className="mb-5 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-primary-on-surface">
            <ArrowUpRight aria-hidden="true" className="size-4" />
            Comunicado oficial
          </p>
          <h1 className="font-heading text-4xl font-medium leading-tight text-white sm:text-6xl">
            O André agora atende pelo WhatsApp.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-white/70">
            Fale com o André Assistente Imobiliário e conte o que procura. Esta
            página reunirá os próximos comunicados sobre o serviço.
          </p>
          <TrackedCta
            href={WHATSAPP_ASSISTANT_URL}
            ctaId="updates_whatsapp"
            className="mt-8"
          >
            Conversar com André no WhatsApp
          </TrackedCta>
          <p className="mt-8 max-w-2xl border-t border-white/15 pt-6 text-sm leading-relaxed text-white/55">
            André Assistente Imobiliário · informações oficiais e atualizações
            serão publicadas neste site.
          </p>
        </div>
      </section>
    </main>
  );
}