import type { Metadata } from "next";
import Link from "next/link";

import { Footer } from "@/components/footer";
import { MarketDashboard } from "@/components/market/market-dashboard";
import { SITE_NAME, SITE_URL } from "@/lib/site";

const title = `Preços de aluguel e venda em Maceió e Recife | ${SITE_NAME}`;
const description =
  "Mediana do preço pedido no OLX de Maceió e Recife, por bairro, com mapa de calor. Aluguel, venda e valor por m².";

export const metadata: Metadata = {
  title: { absolute: title },
  description,
  alternates: { canonical: "/mercado" },
  openGraph: {
    title,
    description,
    url: `${SITE_URL.replace(/\/$/, "")}/mercado`,
    locale: "pt_BR",
    type: "website",
  },
};

export default function MercadoPage() {
  return (
    <div className="flex flex-1 flex-col bg-surface text-white">
      <header className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 pt-8">
        <Link
          href="/"
          className="font-mono text-xs uppercase tracking-[0.2em] text-primary-on-surface hover:text-white"
        >
          {SITE_NAME}
        </Link>
        <div className="flex flex-col gap-2">
          <h1 className="font-heading text-4xl tracking-tight text-white sm:text-5xl">
            Mercado de Maceió e Recife
          </h1>
          <p className="max-w-2xl text-lg text-white/70">
            Preço pedido nos anúncios ativos do OLX: mediana, bairros e mapa de calor.
          </p>
        </div>
      </header>
      <main>
        <MarketDashboard />
      </main>
      <Footer />
    </div>
  );
}
