/** Nome do OLX (já dobrado) → nome oficial do polígono (também dobrado). */

export function foldName(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export const NEIGHBOURHOOD_ALIASES: Record<string, string> = {
  "sitio dos pintos": "sitio dos pintos sao bras",
  "sao bras": "sitio dos pintos sao bras",
  cohab: "cohab ibura de cima",
  "ibura de cima": "cohab ibura de cima",
  tabuleiro: "tabuleiro do martins",
};

export function polygonKey(olxName: string): string {
  const folded = foldName(olxName);
  return NEIGHBOURHOOD_ALIASES[folded] ?? folded;
}
