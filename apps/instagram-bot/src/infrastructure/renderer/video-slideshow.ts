import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

export interface VideoSlideshowOptions {
  slideDurationSeconds?: number;
  fps?: number;
  outputDir?: string;
}

export class VideoSlideshowGenerator {
  private outputDir: string;

  constructor(outputDir?: string) {
    this.outputDir = outputDir || path.resolve(process.cwd(), 'generated-media');
    if (!fs.existsSync(this.outputDir)) {
      try {
        fs.mkdirSync(this.outputDir, { recursive: true });
      } catch {
        // Ignora erro
      }
    }
  }

  isFfmpegAvailable(): boolean {
    try {
      const res = spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' });
      return res.status === 0;
    } catch {
      return false;
    }
  }

  async createSlideshow(
    postId: string,
    imagePaths: string[],
    options: VideoSlideshowOptions = {}
  ): Promise<string> {
    if (!imagePaths || imagePaths.length === 0) {
      throw new Error('[VideoSlideshow] Pelo menos uma imagem é necessária para criar o vídeo.');
    }

    if (!this.isFfmpegAvailable()) {
      throw new Error(
        '[VideoSlideshow] ffmpeg não encontrado no PATH. Instale o ffmpeg para gerar vídeos em --format video.'
      );
    }

    const slideDuration = options.slideDurationSeconds ?? 3;
    const fps = options.fps ?? 30;
    const outDir = options.outputDir || this.outputDir;

    const outputPath = path.join(outDir, `post_${postId}_slideshow.mp4`);
    const concatFilePath = path.join(outDir, `post_${postId}_concat.txt`);

    // Prepara arquivo de concatenação do ffmpeg
    const lines: string[] = [];
    for (const imgPath of imagePaths) {
      const resolved = path.resolve(imgPath);
      lines.push(`file '${resolved.replace(/'/g, "'\\''")}'`);
      lines.push(`duration ${slideDuration}`);
    }
    // O demuxer concat do ffmpeg necessita da repetição do último frame
    const lastImg = path.resolve(imagePaths[imagePaths.length - 1]);
    lines.push(`file '${lastImg.replace(/'/g, "'\\''")}'`);

    fs.writeFileSync(concatFilePath, lines.join('\n'), 'utf-8');

    try {
      const ffmpegArgs = [
        '-y',
        '-f',
        'concat',
        '-safe',
        '0',
        '-i',
        concatFilePath,
        '-vf',
        'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
        '-c:v',
        'libx264',
        '-r',
        String(fps),
        '-pix_fmt',
        'yuv420p',
        outputPath,
      ];

      const result = spawnSync('ffmpeg', ffmpegArgs, {
        encoding: 'utf-8',
        timeout: 60000,
      });

      if (result.status !== 0) {
        throw new Error(
          `[VideoSlideshow] Erro ao executar ffmpeg: ${result.stderr || result.stdout || 'código ' + result.status}`
        );
      }

      return outputPath;
    } finally {
      if (fs.existsSync(concatFilePath)) {
        try {
          fs.unlinkSync(concatFilePath);
        } catch {
          // Ignora
        }
      }
    }
  }
}
