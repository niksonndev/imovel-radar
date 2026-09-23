import { createRequire } from "node:module";
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const pkg = dirname(require.resolve("maplibre-gl/package.json"));
const dest = join(here, "..", "public", "maplibre");
mkdirSync(dest, { recursive: true });

for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(pkg, "dist", file), join(dest, file));
}
