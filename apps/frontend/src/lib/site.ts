// Base URL do site, usada em metadata (canonical, OG, sitemap, robots).
//
// Ordem de resolução:
// 1. NEXT_PUBLIC_SITE_URL — configurada manualmente (ex.: domínio próprio).
// 2. VERCEL_PROJECT_PRODUCTION_URL — URL de produção do projeto na Vercel
//    (ex.: meu-projeto.vercel.app), injetada automaticamente pelo sistema.
// 3. VERCEL_URL — URL do deployment atual na Vercel (fallback).
// 4. Fallback local — apenas para dev/build fora da Vercel.
//
// As variáveis VERCEL_* não precisam ser configuradas: a Vercel as fornece
// automaticamente em todos os planos (requer "System Environment Variables"
// habilitado nas configurações do projeto, que é o padrão).

function normalizeUrl(url: string): string {
  return url.startsWith("http://") || url.startsWith("https://")
    ? url
    : `https://${url}`;
}

const envSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;
const vercelProductionUrl = process.env.VERCEL_PROJECT_PRODUCTION_URL;
const vercelDeploymentUrl = process.env.VERCEL_URL;

const LOCAL_FALLBACK_URL = "https://imovel-radar.vercel.app";

// Fail-fast: se nenhum dos três estiver definido em produção, o domínio usado
// em canonical/sitemap/robots estaria errado. Isso só acontece se as variáveis
// de sistema da Vercel estiverem desabilitadas no projeto.
if (
  !envSiteUrl &&
  !vercelProductionUrl &&
  !vercelDeploymentUrl &&
  process.env.VERCEL_ENV === "production"
) {
  throw new Error(
    "Não foi possível determinar a URL pública do site: defina NEXT_PUBLIC_SITE_URL ou habilite as System Environment Variables do projeto na Vercel."
  );
}

function resolveSiteUrl(): string {
  if (envSiteUrl) return normalizeUrl(envSiteUrl);
  if (vercelProductionUrl) return normalizeUrl(vercelProductionUrl);
  if (vercelDeploymentUrl) return normalizeUrl(vercelDeploymentUrl);
  return LOCAL_FALLBACK_URL;
}

export const SITE_URL = resolveSiteUrl();

if (!envSiteUrl && !vercelProductionUrl && !vercelDeploymentUrl) {
  console.warn(
    `[site] URL pública não definida (NEXT_PUBLIC_SITE_URL/VERCEL_*) — usando fallback de dev (${LOCAL_FALLBACK_URL}). Não use este valor em produção.`
  );
}

export const SITE_NAME = "Imóvel Radar";

export const SITE_DESCRIPTION =
  "Monitore anúncios de imóveis no OLX Maceió e receba alertas no Telegram na hora.";
