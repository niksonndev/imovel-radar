import { foldName } from "@/content/neighbourhood-aliases";

/** Stable URL segment for city keys and neighbourhood names. */
export function slugifyLocation(value: string): string {
  return foldName(value).replace(/\s+/g, "-");
}

export function neighbourhoodSlugFromName(name: string): string {
  return slugifyLocation(name);
}

export function matchesNeighbourhoodSlug(name: string, slug: string): boolean {
  return slugifyLocation(name) === slug;
}
