import { buildSiteJsonLd } from "@/content/ai-seo/ai-serp-features/json-ld";

/** Injects schema.org JSON-LD for AI SERP / rich results. */
export function AiSeoJsonLd() {
  const jsonLd = buildSiteJsonLd();

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
      }}
    />
  );
}
