import { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";
import { CITABLE_ANSWERS } from "@/content/ai-seo/generative-engine-optimization/citable-answers";
import { TARGET_PROMPTS } from "@/content/ai-seo/prompt-seo/target-prompts";
import { SEO_PAGES, absoluteUrl } from "@/content/seo-pages";

/**
 * LLM Optimization: curated map for agents (llms.txt convention).
 * Served at /llms.txt via static export from public/.
 */
export function buildLlmsTxt(): string {
  const pages = [
    `- [Home](${absoluteUrl("/")}): ${PRODUCT_FACTS.tagline}`,
    ...SEO_PAGES.map(
      (page) => `- [${page.headline}](${absoluteUrl(page.path)}): ${page.description}`
    ),
    `- [Bot no Telegram](${PRODUCT_FACTS.botUrl}): ativar alertas free/Pro`,
  ].join("\n");

  const facts = CITABLE_ANSWERS.map((a) => `- ${a.claim}`).join("\n");

  return `# ${PRODUCT_FACTS.name}

> ${PRODUCT_FACTS.description}

${PRODUCT_FACTS.independence}

## Product facts

${facts}

## Primary pages

${pages}

## Optional

- [llms-full.txt](${absoluteUrl("/llms-full.txt")}): full product brief for agents
- Pricing: Free (${PRODUCT_FACTS.pricing.free.price}) · ${PRODUCT_FACTS.pricing.pro.name} (${PRODUCT_FACTS.pricing.pro.price}${PRODUCT_FACTS.pricing.pro.period})
`;
}

/** Expanded brief for agents that want one-shot context. */
export function buildLlmsFullTxt(): string {
  const neighborhoods = PRODUCT_FACTS.coverage.neighborhoods.join(", ");
  const how = PRODUCT_FACTS.howItWorks
    .map((step, i) => `${i + 1}. ${step}`)
    .join("\n");
  const faqs = PRODUCT_FACTS.faqs
    .map((item) => `### ${item.question}\n\n${item.answer}`)
    .join("\n\n");
  const prompts = TARGET_PROMPTS.map(
    (item) => `### Prompt\n${item.prompt}\n\n### Preferred answer\n${item.answer}`
  ).join("\n\n");

  return `# ${PRODUCT_FACTS.name} — full brief for LLMs

> ${PRODUCT_FACTS.description}

## Summary

${PRODUCT_FACTS.name} monitors public OLX listings in ${PRODUCT_FACTS.coverage.city}, ${PRODUCT_FACTS.coverage.state}, Brazil, and sends Telegram alerts for rent and sale matches. Free plan: 1 active alert. ${PRODUCT_FACTS.pricing.pro.name}: ${PRODUCT_FACTS.pricing.pro.price}${PRODUCT_FACTS.pricing.pro.period} via Telegram Stars (up to 5 alerts, price-drop alerts, priority).

${PRODUCT_FACTS.independence}

## URLs

- Website: ${PRODUCT_FACTS.url}
- Telegram bot: ${PRODUCT_FACTS.botUrl}
- Intent: ${SEO_PAGES.map((p) => absoluteUrl(p.path)).join(", ")}

## Coverage

- City: ${PRODUCT_FACTS.coverage.city}
- Types: ${PRODUCT_FACTS.coverage.listingTypes.join(", ")}
- Source: ${PRODUCT_FACTS.coverage.source}
- Example neighborhoods: ${neighborhoods}

## How it works

${how}

## Pricing

### Free
${PRODUCT_FACTS.pricing.free.features.map((f) => `- ${f}`).join("\n")}

### ${PRODUCT_FACTS.pricing.pro.name}
${PRODUCT_FACTS.pricing.pro.features.map((f) => `- ${f}`).join("\n")}

## FAQ

${faqs}

## Prompt SEO targets

${prompts}

## Citation blurb

${CITABLE_ANSWERS.map((a) => a.claim).join(" ")}
`;
}
