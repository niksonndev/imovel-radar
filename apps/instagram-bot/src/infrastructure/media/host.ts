import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { isPublicHttpUrl, mimeForFile } from './files.js';

export interface ServedMedia {
  urls: string[];
  close: () => Promise<void>;
}

function tryCloudflared(localPort: number): Promise<{ base: string; proc: ChildProcess } | null> {
  return new Promise((resolve) => {
    let proc: ChildProcess;
    try {
      proc = spawn('cloudflared', ['tunnel', '--url', `http://127.0.0.1:${localPort}`], {
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch {
      resolve(null);
      return;
    }

    const timeout = setTimeout(() => {
      proc.kill();
      resolve(null);
    }, 20_000);

    const onData = (chunk: Buffer) => {
      const text = chunk.toString();
      const match = text.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/i);
      if (match) {
        clearTimeout(timeout);
        proc.stdout?.off('data', onData);
        proc.stderr?.off('data', onData);
        resolve({ base: match[0], proc });
      }
    };

    proc.stdout?.on('data', onData);
    proc.stderr?.on('data', onData);
    proc.on('error', () => {
      clearTimeout(timeout);
      resolve(null);
    });
    proc.on('exit', () => {
      clearTimeout(timeout);
    });
  });
}

export class MediaHost {
  async serve(filePaths: string[]): Promise<ServedMedia> {
    const files = new Map<string, string>();
    for (const abs of filePaths) {
      const key = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}_${path.basename(abs)}`;
      files.set(key, abs);
    }

    const server = http.createServer((req, res) => {
      const name = decodeURIComponent((req.url || '/').replace(/^\//, '').split('?')[0]);
      const file = files.get(name);
      if (!file || !fs.existsSync(file)) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, { 'Content-Type': mimeForFile(file) });
      fs.createReadStream(file).pipe(res);
    });

    const port = await new Promise<number>((resolve, reject) => {
      server.listen(Number(process.env.MEDIA_PORT) || 0, '0.0.0.0', () => {
        const addr = server.address();
        if (!addr || typeof addr === 'string') {
          reject(new Error('Falha ao iniciar servidor local de mídia.'));
          return;
        }
        resolve(addr.port);
      });
    });

    let tunnelProc: ChildProcess | undefined;
    const configured = process.env.PUBLISH_BASE_URL?.replace(/\/$/, '');
    let publicBase: string;

    if (configured && isPublicHttpUrl(configured)) {
      publicBase = configured;
      console.log(`[MediaHost] Usando PUBLISH_BASE_URL=${publicBase} (porta local ${port})`);
    } else {
      const tunnel = await tryCloudflared(port);
      if (!tunnel) {
        server.close();
        throw new Error(
          `A API precisa baixar o arquivo por HTTPS público. Servidor local na porta ${port}, mas sem túnel.\n` +
            `Instale o cloudflared (Cloudflare Tunnel) ou defina PUBLISH_BASE_URL para um túnel (ngrok etc.) apontando para essa porta.`
        );
      }
      tunnelProc = tunnel.proc;
      publicBase = tunnel.base;
      console.log(`[MediaHost] Túnel público: ${publicBase}`);
    }

    const urls = [...files.keys()].map(
      (key) => `${publicBase}/${encodeURIComponent(key)}`
    );

    return {
      urls,
      close: async () => {
        tunnelProc?.kill();
        await new Promise<void>((resolve) => {
          server.close(() => resolve());
        });
      },
    };
  }
}
