import fs from 'node:fs';
import path from 'node:path';

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.gif', '.webp']);
const VIDEO_EXTS = new Set(['.mp4', '.mov', '.m4v', '.webm']);

export type LocalMediaKind = 'image' | 'video';

export function mimeForFile(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const map: Record<string, string> = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.m4v': 'video/mp4',
    '.webm': 'video/webm',
  };
  return map[ext] || 'application/octet-stream';
}

export function classifyLocalFile(filePath: string): LocalMediaKind {
  const ext = path.extname(filePath).toLowerCase();
  if (IMAGE_EXTS.has(ext)) return 'image';
  if (VIDEO_EXTS.has(ext)) return 'video';
  throw new Error(
    `Tipo de arquivo não suportado (${ext || 'sem extensão'}): ${filePath}. Use jpg/png/webp ou mp4/mov.`
  );
}

export function resolveExistingFile(filePath: string): string {
  const abs = path.resolve(filePath);
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
    throw new Error(`Arquivo não encontrado: ${filePath}`);
  }
  return abs;
}

export function isPublicHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return false;
    return !['localhost', '127.0.0.1', '::1'].includes(url.hostname);
  } catch {
    return false;
  }
}

export function isLiveMode(platform: 'instagram' | 'tiktok'): boolean {
  const key = platform === 'tiktok' ? 'TIKTOK_MODE' : 'INSTAGRAM_MODE';
  return (process.env[key] || 'MOCK').toUpperCase() === 'LIVE';
}
