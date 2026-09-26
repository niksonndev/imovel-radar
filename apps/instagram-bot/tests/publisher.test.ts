import { describe, it, expect, vi } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { LocalPublisher } from '../src/agents/publisher/index.js';
import { MockInstagramClient } from '../src/infrastructure/instagram/mock-client.js';
import { MockTikTokClient } from '../src/infrastructure/tiktok/mock-client.js';
import { MediaHost } from '../src/infrastructure/media/host.js';

function writeTemp(name: string, contents: string): string {
  const file = path.join(os.tmpdir(), `ir-media-${Date.now()}-${name}`);
  fs.writeFileSync(file, contents);
  return file;
}

describe('LocalPublisher', () => {
  it('publica foto única e carrossel no mock do Instagram', async () => {
    const state = path.join(os.tmpdir(), `.test-ig-pub-${Date.now()}.json`);
    const client = new MockInstagramClient(state);
    const publisher = new LocalPublisher(client);
    const a = writeTemp('a.jpg', 'fake-jpg-a');
    const b = writeTemp('b.jpg', 'fake-jpg-b');

    const single = await publisher.publish({ files: [a], caption: 'Foto avulsa' });
    expect(single.mediaId).toBeDefined();

    const carousel = await publisher.publish({ files: [a, b], caption: 'Carrossel local' });
    expect(carousel.mediaId).toBeDefined();

    const media = await client.getRecentMedia(5);
    expect(media[0].caption).toBe('Carrossel local');
    expect(media[0].mediaType).toBe('CAROUSEL_ALBUM');
  });

  it('publica vídeo local no Instagram mock', async () => {
    const state = path.join(os.tmpdir(), `.test-ig-vid-${Date.now()}.json`);
    const client = new MockInstagramClient(state);
    const publisher = new LocalPublisher(client);
    const video = writeTemp('clip.mp4', 'fake-mp4');

    const res = await publisher.publish({ files: [video], caption: 'Reel local' });
    expect(res.mediaId).toBeDefined();
    const media = await client.getRecentMedia(1);
    expect(media[0].mediaType).toBe('VIDEO');
  });

  it('publica vídeo local no TikTok mock', async () => {
    const state = path.join(os.tmpdir(), `.test-tt-vid-${Date.now()}.json`);
    const client = new MockTikTokClient(state);
    const publisher = new LocalPublisher(client);
    const video = writeTemp('tt.mp4', 'fake-mp4');

    const res = await publisher.publish({ files: [video], caption: 'TikTok local' });
    expect(res.mediaId).toBeDefined();
  });

  it('recusa misturar foto e vídeo', async () => {
    const client = new MockInstagramClient(path.join(os.tmpdir(), `.test-mix-${Date.now()}.json`));
    const publisher = new LocalPublisher(client);
    const img = writeTemp('x.jpg', 'img');
    const vid = writeTemp('y.mp4', 'vid');
    await expect(
      publisher.publish({ files: [img, vid], caption: 'nope' })
    ).rejects.toThrow(/Não misture/);
  });

  it('não chama MediaHost em modo MOCK', async () => {
    const serve = vi.fn();
    const client = new MockInstagramClient(path.join(os.tmpdir(), `.test-host-${Date.now()}.json`));
    const publisher = new LocalPublisher(client, { serve } as unknown as MediaHost);
    const img = writeTemp('z.jpg', 'img');
    await publisher.publish({ files: [img], caption: 'mock' });
    expect(serve).not.toHaveBeenCalled();
  });
});
