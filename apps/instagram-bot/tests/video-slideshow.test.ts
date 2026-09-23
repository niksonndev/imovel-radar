import { describe, it, expect, afterAll } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { VideoSlideshowGenerator } from '../src/infrastructure/renderer/video-slideshow.js';
import { CardGenerator } from '../src/infrastructure/renderer/card-generator.js';

describe('VideoSlideshowGenerator', () => {
  const tmpDir = path.resolve(process.cwd(), 'generated-media', 'test-slideshow');
  const generator = new VideoSlideshowGenerator(tmpDir);
  const cardGen = new CardGenerator();

  afterAll(() => {
    if (fs.existsSync(tmpDir)) {
      try {
        fs.rmSync(tmpDir, { recursive: true, force: true });
      } catch {
        // ignore
      }
    }
  });

  it('deve verificar disponibilidade do ffmpeg', () => {
    const available = generator.isFfmpegAvailable();
    expect(typeof available).toBe('boolean');
  });

  it('deve lançar erro se lista de imagens for vazia', async () => {
    await expect(generator.createSlideshow('test-empty', [])).rejects.toThrow(
      'Pelo menos uma imagem é necessária'
    );
  });

  it('deve criar um vídeo MP4 9:16 a partir de imagens PNG quando ffmpeg estiver disponível', async () => {
    if (!generator.isFfmpegAvailable()) {
      console.warn('ffmpeg não disponível no ambiente, pulando teste de geração de vídeo.');
      return;
    }

    if (!fs.existsSync(tmpDir)) {
      fs.mkdirSync(tmpDir, { recursive: true });
    }

    // Gerar 2 imagens PNG de teste (9:16 TikTok)
    const svg1 = `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920">
      <rect width="1080" height="1920" fill="#0A0F1D"/>
      <text x="100" y="300" fill="#FFFFFF" font-size="60">Slide 1 TikTok</text>
    </svg>`;

    const svg2 = `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920">
      <rect width="1080" height="1920" fill="#111827"/>
      <text x="100" y="300" fill="#F59E0B" font-size="60">Slide 2 TikTok</text>
    </svg>`;

    const png1Path = path.join(tmpDir, 'slide_1.png');
    const png2Path = path.join(tmpDir, 'slide_2.png');

    cardGen.rasterizeSvgToPng(svg1, png1Path);
    cardGen.rasterizeSvgToPng(svg2, png2Path);

    // Gerar slideshow de 1 segundo por slide para ser rápido no teste
    const videoPath = await generator.createSlideshow('test_post_123', [png1Path, png2Path], {
      slideDurationSeconds: 1,
      fps: 24,
      outputDir: tmpDir,
    });

    expect(fs.existsSync(videoPath)).toBe(true);
    expect(videoPath.endsWith('.mp4')).toBe(true);

    const stat = fs.statSync(videoPath);
    expect(stat.size).toBeGreaterThan(1000); // Mais de 1KB de vídeo válido
  });
});
