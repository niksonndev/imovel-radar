export type DemoRole = "bot" | "user";

export type SummaryRow = {
  icon: string;
  label: string;
  value: string;
};

/** Confirmation order from the real wizard summary. */
export const ALERT_SUMMARY: readonly SummaryRow[] = [
  { icon: "🏷️", label: "Tipo", value: "Alugar" },
  { icon: "💰", label: "Preço", value: "R$ 2.000,00 – R$ 2.500,00" },
  { icon: "🛏", label: "Quartos", value: "3+" },
  { icon: "🏠", label: "Categoria", value: "Apartamento" },
  { icon: "📍", label: "Bairros", value: "Antares, Serraria" },
  { icon: "📝", label: "Nome", value: "Novo apê" },
];

export const LISTING = {
  title: "Apartamento 3 quartos em Antares",
  price: "R$ 2.300,00",
  rooms: "3 quarto(s)",
  area: "72m²",
  neighbourhood: "Antares",
  kind: "Aluguel",
  counter: "1 de 2",
  time: "10:15",
} as const;

type TextStep = {
  id: string;
  kind: "text";
  role: DemoRole;
  title?: string;
  body: string;
  time: string;
  /** When false, a bot line arrives without the typing indicator. */
  typing?: boolean;
  pauseAfter?: number;
};

type ConfirmStep = {
  id: "confirm";
  kind: "confirm";
  role: "bot";
  time: string;
};

type ListingStep = {
  id: "listing";
  kind: "listing";
  role: "bot";
  typing: false;
  time: string;
};

export type DemoStep = TextStep | ConfirmStep | ListingStep;

/**
 * Wizard order from create_new_alert: kind, category, price, rooms,
 * neighbourhoods, name, confirm, search, then the matching listing.
 * Prompts follow the bot copy in handlers/ui/menus.py.
 */
export const DEMO_STEPS: readonly DemoStep[] = [
  {
    id: "kind",
    kind: "text",
    role: "bot",
    title: "🆕 Novo alerta",
    body: "O que você procura?",
    time: "10:12",
  },
  {
    id: "kind-reply",
    kind: "text",
    role: "user",
    body: "Alugar",
    time: "10:12",
  },
  {
    id: "category",
    kind: "text",
    role: "bot",
    title: "🏠 Tipo de imóvel",
    body: "Toque para selecionar (pode marcar mais de um). Sem seleção = qualquer tipo.",
    time: "10:12",
  },
  {
    id: "category-reply",
    kind: "text",
    role: "user",
    body: "Apartamento",
    time: "10:12",
  },
  {
    id: "price",
    kind: "text",
    role: "bot",
    title: "💰 Faixa de preço (aluguel)",
    body: "Toque em uma opção ou Personalizado.",
    time: "10:13",
  },
  {
    id: "price-reply",
    kind: "text",
    role: "user",
    body: "R$ 2.000,00 – R$ 2.500,00",
    time: "10:13",
  },
  {
    id: "rooms",
    kind: "text",
    role: "bot",
    title: "🛏 Quartos",
    body: "Mínimo de quartos que você quer?",
    time: "10:13",
  },
  {
    id: "rooms-reply",
    kind: "text",
    role: "user",
    body: "3+",
    time: "10:13",
  },
  {
    id: "neighbourhoods",
    kind: "text",
    role: "bot",
    title: "📍 Bairros",
    body: "Bairros selecionados: nenhum ainda. Toque em mais bairros ou conclua.",
    time: "10:13",
  },
  {
    id: "neighbourhoods-reply",
    kind: "text",
    role: "user",
    body: "Antares, Serraria",
    time: "10:14",
  },
  {
    id: "name",
    kind: "text",
    role: "bot",
    body: "Agora, envie o nome do alerta (ex.: Aluguel Centro).",
    time: "10:14",
  },
  {
    id: "name-reply",
    kind: "text",
    role: "user",
    body: "Novo apê",
    time: "10:14",
  },
  {
    id: "confirm",
    kind: "confirm",
    role: "bot",
    time: "10:14",
  },
  {
    id: "confirm-reply",
    kind: "text",
    role: "user",
    body: "Confirmar",
    time: "10:14",
  },
  {
    id: "search",
    kind: "text",
    role: "bot",
    body: "⏳ Procurando imóveis que combinam com seu alerta…",
    time: "10:14",
    pauseAfter: 1.05,
  },
  {
    id: "listing",
    kind: "listing",
    role: "bot",
    typing: false,
    time: LISTING.time,
  },
];
