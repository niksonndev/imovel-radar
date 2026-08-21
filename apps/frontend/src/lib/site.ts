// Base URL do site, usada em metadata (canonical, OG, sitemap, robots).
// Configure NEXT_PUBLIC_SITE_URL no build/deploy com o domínio de produção.
const envSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;

// Fail-fast: em deploy de produção (Vercel) não há fallback silencioso — um
// domínio errado vazaria para canonical, sitemap e robots. Fora disso (build
// local, preview), o placeholder é aceitável e apenas um aviso é emitido.
if (!envSiteUrl && process.env.VERCEL_ENV === "production") {
  throw new Error(
    "NEXT_PUBLIC_SITE_URL não está definida. Configure-a nas variáveis de ambiente do deploy de produção (ex.: https://imovelradar.com.br)."
  );
}

export const SITE_URL = envSiteUrl ?? "https://imovel-radar.com.br";

if (!envSiteUrl) {
  console.warn(
    "[site] NEXT_PUBLIC_SITE_URL não definida — usando fallback de dev (https://imovel-radar.com.br). Não use este valor em produção."
  );
}

export const SITE_NAME = "Imóvel Radar";

export const SITE_DESCRIPTION =
  "Monitore anúncios de imóveis no OLX Maceió e receba alertas no Telegram na hora.";
