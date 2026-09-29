"""
Transcrição de áudio do usuário (Fase 3) via OpenAI Whisper.

``transcribe_audio`` converte bytes de áudio em texto. Falha de forma graciosa
retorna ``None`` para o assistente cair num fallback amigável.
"""

from __future__ import annotations

import logging
import mimetypes

import httpx

logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-1"


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    api_key: str,
    model: str = WHISPER_MODEL,
    timeout_s: float = 30.0,
    filename: str = "audio.ogg",
    content_type: str | None = None,
) -> str | None:
    """Envia o áudio para a OpenAI e retorna o texto transcrito (ou None)."""
    if not audio_bytes or not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={
                    "file": (
                        filename,
                        audio_bytes,
                        content_type
                        or mimetypes.guess_type(filename)[0]
                        or "application/octet-stream",
                    )
                },
                data={"model": model},
            )
            if resp.status_code != 200:
                logger.warning("Whisper retornou %s: %s", resp.status_code, resp.text[:300])
                return None
            text = resp.json().get("text", "").strip()
            return text or None
    except httpx.TimeoutException:
        logger.warning("Timeout (%.1fs) transcrevendo áudio", timeout_s)
        return None
    except Exception:
        logger.exception("Falha inesperada ao transcrever áudio")
        return None
