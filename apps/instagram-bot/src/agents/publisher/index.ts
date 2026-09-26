import {
  PublishResult,
  SocialClient,
  SocialPlatform,
} from '../../infrastructure/social/types.js';
import {
  classifyLocalFile,
  isLiveMode,
  isPublicHttpUrl,
  resolveExistingFile,
} from '../../infrastructure/media/files.js';
import { MediaHost } from '../../infrastructure/media/host.js';

export interface LocalPublishInput {
  files?: string[];
  urls?: string[];
  caption: string;
}

export class LocalPublisher {
  constructor(
    private client: SocialClient,
    private mediaHost: MediaHost = new MediaHost()
  ) {}

  async publish(input: LocalPublishInput): Promise<PublishResult> {
    const caption = input.caption.trim();
    if (!caption) {
      throw new Error('Informe uma legenda com --caption.');
    }

    const localFiles = (input.files || []).map(resolveExistingFile);
    const remoteUrls = (input.urls || []).filter(Boolean);

    if (localFiles.length === 0 && remoteUrls.length === 0) {
      throw new Error('Informe pelo menos um arquivo (--file) ou URL pública (--url).');
    }

    const remoteKinds = remoteUrls.map((url) => {
      if (!isPublicHttpUrl(url)) {
        throw new Error(`URL precisa ser HTTP(S) pública: ${url}`);
      }
      const lower = url.toLowerCase();
      if (/\.(mp4|mov|m4v|webm)(\?|$)/.test(lower)) return 'video' as const;
      return 'image' as const;
    });
    const localKinds = localFiles.map(classifyLocalFile);

    const imageFiles = localFiles.filter((_, i) => localKinds[i] === 'image');
    const videoFiles = localFiles.filter((_, i) => localKinds[i] === 'video');
    const imageUrls = remoteUrls.filter((_, i) => remoteKinds[i] === 'image');
    const videoUrls = remoteUrls.filter((_, i) => remoteKinds[i] === 'video');

    const totalVideos = videoFiles.length + videoUrls.length;
    const totalImages = imageFiles.length + imageUrls.length;

    if (totalVideos > 0 && totalImages > 0) {
      throw new Error('Não misture foto e vídeo no mesmo comando. Publique um Reels/vídeo ou um carrossel de fotos.');
    }
    if (totalVideos > 1) {
      throw new Error('Envie um único arquivo de vídeo por publicação.');
    }

    if (totalVideos === 1) {
      if (videoUrls.length === 1) {
        return this.client.publishVideo(caption, videoUrls[0]);
      }
      if (this.client.capabilities.videoFromFile) {
        return this.client.publishVideoFromFile(caption, videoFiles[0]);
      }
      const hosted = await this.hostLocalImagesIfNeeded(videoFiles);
      try {
        return this.client.publishVideo(caption, hosted.urls[0]);
      } finally {
        await hosted.close();
      }
    }

    const hosted = await this.hostLocalImagesIfNeeded(imageFiles);
    try {
      const allImageUrls = [...hosted.urls, ...imageUrls];
      if (allImageUrls.length === 1) {
        return this.client.publishPost(caption, allImageUrls[0]);
      }
      return this.client.publishCarousel(caption, allImageUrls);
    } finally {
      await hosted.close();
    }
  }

  private async hostLocalImagesIfNeeded(
    imageFiles: string[]
  ): Promise<{ urls: string[]; close: () => Promise<void> }> {
    if (imageFiles.length === 0) {
      return { urls: [], close: async () => undefined };
    }

    const live = isLiveMode(this.client.platform as SocialPlatform);
    if (!live) {
      return {
        urls: imageFiles,
        close: async () => undefined,
      };
    }

    return this.mediaHost.serve(imageFiles);
  }
}
