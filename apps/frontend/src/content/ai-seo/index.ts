/**
 * AI SEO content modules
 *
 * ├── generative-engine-optimization/  — entity + citable answers (GEO)
 * ├── llm-optimization/                — llms.txt / llms-full.txt builders
 * ├── ai-content/                      — canonical product facts
 * ├── ai-serp-features/                — JSON-LD rich results
 * └── prompt-seo/                      — target prompts + preferred answers
 */

export { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";
export { BRAND_ENTITY } from "@/content/ai-seo/generative-engine-optimization/brand-entity";
export { CITABLE_ANSWERS } from "@/content/ai-seo/generative-engine-optimization/citable-answers";
export { buildSiteJsonLd } from "@/content/ai-seo/ai-serp-features/json-ld";
export {
  buildLlmsTxt,
  buildLlmsFullTxt,
} from "@/content/ai-seo/llm-optimization/llms-txt";
export { TARGET_PROMPTS } from "@/content/ai-seo/prompt-seo/target-prompts";
