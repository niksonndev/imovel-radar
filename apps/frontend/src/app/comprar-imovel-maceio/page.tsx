import type { Metadata } from "next";
import { IntentLanding } from "@/components/intent-landing";
import { getSeoPage } from "@/content/seo-pages";
import { SITE_URL } from "@/lib/site";

const page = getSeoPage("comprar-imovel-maceio")!;

export const metadata: Metadata = {
  title: { absolute: page.title },
  description: page.description,
  keywords: [...page.keywords],
  alternates: { canonical: page.path },
  openGraph: {
    title: page.title,
    description: page.description,
    url: `${SITE_URL}${page.path}`,
    locale: "pt_BR",
    type: "website",
  },
};

export default function ComprarImovelMaceioPage() {
  return <IntentLanding page={page} />;
}
