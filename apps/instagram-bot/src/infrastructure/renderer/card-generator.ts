import fs from 'node:fs';
import path from 'node:path';

export interface SlideContent {
  slideNumber: number;
  totalSlides: number;
  title: string;
  body: string;
  highlightedMetric?: string;
  tag?: string;
}

export interface RenderResult {
  slideNumber: number;
  svgContent: string;
  filePath: string;
}

export class CardGenerator {
  private outputDir: string;

  constructor(outputDir?: string) {
    this.outputDir = outputDir || path.resolve(process.cwd(), 'generated-media');
    if (!fs.existsSync(this.outputDir)) {
      try {
        fs.mkdirSync(this.outputDir, { recursive: true });
      } catch {
        // Ignora erro se já existir
      }
    }
  }

  generateSlideSvg(slide: SlideContent): string {
    const isCover = slide.slideNumber === 1;
    const isLast = slide.slideNumber === slide.totalSlides;

    const escapeXml = (unsafe: string) =>
      unsafe
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');

    const title = escapeXml(slide.title);
    const body = escapeXml(slide.body);
    const metric = slide.highlightedMetric ? escapeXml(slide.highlightedMetric) : '';
    const tag = slide.tag ? escapeXml(slide.tag) : 'IMOVEL RADAR • MACEIÓ';

    if (isCover) {
      return `
<svg width="1080" height="1350" viewBox="0 0 1080 1350" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#090D16" />
      <stop offset="60%" stop-color="#0E1626" />
      <stop offset="100%" stop-color="#08233D" />
    </linearGradient>
    <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38BDF8" />
      <stop offset="100%" stop-color="#818CF8" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="60" result="blur" />
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1080" height="1350" fill="url(#bgGrad)" />

  <!-- Ambient Light Orbs -->
  <circle cx="850" cy="250" r="280" fill="#0284C7" opacity="0.25" filter="url(#glow)" />
  <circle cx="200" cy="1000" r="320" fill="#4F46E5" opacity="0.2" filter="url(#glow)" />

  <!-- Header Badge -->
  <g transform="translate(80, 100)">
    <rect width="360" height="48" rx="24" fill="#1E293B" stroke="#334155" stroke-width="2" />
    <circle cx="28" cy="24" r="8" fill="#10B981" />
    <text x="50" y="31" fill="#94A3B8" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700" letter-spacing="2">
      ${tag}
    </text>
  </g>

  <!-- Card Frame -->
  <rect x="80" y="240" width="920" height="880" rx="40" fill="#0F172A" fill-opacity="0.8" stroke="#1E293B" stroke-width="3" />

  <!-- Main Hook / Title -->
  <text x="140" y="440" fill="#F8FAFC" font-family="system-ui, -apple-system, sans-serif" font-size="64" font-weight="800" width="800">
    <tspan x="140" dy="0">${title.slice(0, 30)}</tspan>
    <tspan x="140" dy="75">${title.slice(30, 65)}</tspan>
  </text>

  <!-- Metric Highlight Box -->
  ${
    metric
      ? `
  <g transform="translate(140, 620)">
    <rect width="800" height="140" rx="24" fill="#0284C7" fill-opacity="0.15" stroke="#38BDF8" stroke-width="2" />
    <text x="40" y="85" fill="#38BDF8" font-family="system-ui, -apple-system, sans-serif" font-size="44" font-weight="800">
      ${metric}
    </text>
  </g>
  `
      : ''
  }

  <!-- Body copy -->
  <text x="140" y="850" fill="#94A3B8" font-family="system-ui, -apple-system, sans-serif" font-size="32" font-weight="400">
    <tspan x="140" dy="0">${body.slice(0, 50)}</tspan>
    <tspan x="140" dy="48">${body.slice(50, 110)}</tspan>
  </text>

  <!-- Footer Navigation Indicator -->
  <g transform="translate(80, 1200)">
    <text x="0" y="30" fill="#64748B" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="600">
      Arraste para o lado 👉
    </text>
    <text x="860" y="30" fill="#64748B" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="600">
      1/${slide.totalSlides}
    </text>
  </g>
</svg>
`.trim();
    }

    if (isLast) {
      return `
<svg width="1080" height="1350" viewBox="0 0 1080 1350" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradLast" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#08233D" />
      <stop offset="100%" stop-color="#020617" />
    </linearGradient>
    <filter id="glowLast" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="80" result="blur" />
    </filter>
  </defs>

  <rect width="1080" height="1350" fill="url(#bgGradLast)" />
  <circle cx="540" cy="500" r="300" fill="#0284C7" opacity="0.3" filter="url(#glowLast)" />

  <!-- CTA Box -->
  <rect x="80" y="160" width="920" height="1020" rx="40" fill="#0F172A" fill-opacity="0.9" stroke="#38BDF8" stroke-width="3" />

  <g transform="translate(540, 360)">
    <!-- Telegram / Bot Icon Circle -->
    <circle cx="0" cy="0" r="80" fill="#0284C7" />
    <path d="M-30 0 L25 -25 L0 30 L-8 8 Z" fill="#FFFFFF" />
  </g>

  <text x="540" y="520" text-anchor="middle" fill="#F8FAFC" font-family="system-ui, -apple-system, sans-serif" font-size="52" font-weight="800">
    Ative seu Alerta Grátis
  </text>

  <text x="540" y="600" text-anchor="middle" fill="#94A3B8" font-family="system-ui, -apple-system, sans-serif" font-size="30" font-weight="400">
    Receba imóveis em Maceió direto no Telegram
  </text>

  <!-- Big CTA Button -->
  <g transform="translate(190, 720)">
    <rect width="700" height="120" rx="60" fill="#0284C7" />
    <text x="350" y="74" text-anchor="middle" fill="#FFFFFF" font-family="system-ui, -apple-system, sans-serif" font-size="38" font-weight="800">
      COMENTE "ALERTA"
    </text>
  </g>

  <text x="540" y="940" text-anchor="middle" fill="#38BDF8" font-family="system-ui, -apple-system, sans-serif" font-size="34" font-weight="700">
    ou busque por @imovelradar_bot
  </text>

  <text x="540" y="1250" text-anchor="middle" fill="#64748B" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="600">
    ${slide.slideNumber}/${slide.totalSlides} • Imóvel Radar Maceió
  </text>
</svg>
`.trim();
    }

    // Slide de Conteúdo / Ranking
    return `
<svg width="1080" height="1350" viewBox="0 0 1080 1350" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradContent" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0B132B" />
      <stop offset="100%" stop-color="#1C2541" />
    </linearGradient>
  </defs>

  <rect width="1080" height="1350" fill="url(#bgGradContent)" />

  <!-- Top Bar -->
  <g transform="translate(80, 100)">
    <text x="0" y="30" fill="#38BDF8" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="700" letter-spacing="2">
      ${tag}
    </text>
  </g>

  <!-- Slide Card -->
  <rect x="80" y="180" width="920" height="980" rx="36" fill="#0B1329" stroke="#1E293B" stroke-width="2" />

  <!-- Slide Title -->
  <text x="140" y="300" fill="#F8FAFC" font-family="system-ui, -apple-system, sans-serif" font-size="46" font-weight="800">
    ${title}
  </text>

  <!-- Metric Banner if present -->
  ${
    metric
      ? `
  <g transform="translate(140, 360)">
    <rect width="800" height="90" rx="18" fill="#1E293B" stroke="#38BDF8" stroke-width="1.5" />
    <text x="40" y="58" fill="#38BDF8" font-family="system-ui, -apple-system, sans-serif" font-size="34" font-weight="700">
      ${metric}
    </text>
  </g>
  `
      : ''
  }

  <!-- Body Content -->
  <foreignObject x="140" y="${metric ? 490 : 380}" width="800" height="580">
    <div xmlns="http://www.w3.org/1999/xhtml" style="color: #CBD5E1; font-family: system-ui, -apple-system, sans-serif; font-size: 32px; line-height: 1.6; white-space: pre-wrap;">
      ${body}
    </div>
  </foreignObject>

  <!-- Footer -->
  <g transform="translate(80, 1220)">
    <text x="0" y="30" fill="#64748B" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="600">
      Imóvel Radar Maceió
    </text>
    <text x="860" y="30" fill="#64748B" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="600">
      ${slide.slideNumber}/${slide.totalSlides}
    </text>
  </g>
</svg>
`.trim();
  }

  async generateCarouselSlides(
    postId: string,
    slides: Array<{ title: string; body: string; highlightedMetric?: string }>
  ): Promise<RenderResult[]> {
    const results: RenderResult[] = [];
    const totalSlides = slides.length;

    for (let i = 0; i < totalSlides; i++) {
      const slide = slides[i];
      const slideNumber = i + 1;
      const svg = this.generateSlideSvg({
        slideNumber,
        totalSlides,
        title: slide.title,
        body: slide.body,
        highlightedMetric: slide.highlightedMetric,
      });

      const fileName = `post_${postId}_slide_${slideNumber}.svg`;
      const filePath = path.join(this.outputDir, fileName);

      try {
        fs.writeFileSync(filePath, svg, 'utf-8');
      } catch {
        // Fallback para ambientes sem escrita
      }

      results.push({
        slideNumber,
        svgContent: svg,
        filePath,
      });
    }

    return results;
  }
}
