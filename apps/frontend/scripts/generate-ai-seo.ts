import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  buildLlmsFullTxt,
  buildLlmsTxt,
} from "../src/content/ai-seo/llm-optimization/llms-txt";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const publicDir = join(root, "public");

mkdirSync(publicDir, { recursive: true });
writeFileSync(join(publicDir, "llms.txt"), buildLlmsTxt(), "utf8");
writeFileSync(join(publicDir, "llms-full.txt"), buildLlmsFullTxt(), "utf8");

console.log("Wrote public/llms.txt and public/llms-full.txt");
