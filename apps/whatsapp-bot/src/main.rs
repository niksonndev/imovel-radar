use std::sync::Arc;
use std::time::Duration;

use chrono::Utc;
use whatsapp_bot::config::{ensure_parent_dir, Config};
use whatsapp_bot::ai::transcribe_audio;
use whatsapp_bot::db::Db;
use whatsapp_bot::handlers::{handle_text, handle_transcribed_audio, should_show_typing};
use whatsapp_bot::http;
use whatsapp_bot::jobs::{due, now_maceio, read_stamp, run_daily, write_stamp, Sender};
use whatsapp_bot::wa::{qr_ascii, Pairing, WaSender};
use whatsapp_rust::bot::{Bot, EventDelivery};
use whatsapp_rust::prelude::*;
use whatsapp_rust::store::SqliteStore;
use whatsapp_rust::wacore_binary::JidExt;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cfg = Arc::new(Config::from_env()?);
    tracing_subscriber::fmt()
        .with_env_filter(cfg.log_filter())
        .init();
    ensure_parent_dir(&cfg.session_path)?;
    ensure_parent_dir(&cfg.notify_stamp_path)?;

    let db = Db::connect(&cfg.database_url).await?;
    let http_client = reqwest::Client::builder()
        .timeout(Duration::from_secs(20))
        .build()?;
    let pairing = Arc::new(Pairing::default());

    let port = cfg.port;
    let secret = cfg.pair_secret.clone();
    let pairing_http = pairing.clone();
    let http_task = tokio::spawn(async move {
        if let Err(error) = http::serve(port, pairing_http, secret).await {
            tracing::error!(%error, "http encerrou");
        }
    });

    let backend = SqliteStore::new(&cfg.session_path).await?;
    let pairing_qr = pairing.clone();
    let pairing_events = pairing.clone();
    let message_db = db.clone();
    let message_cfg = cfg.clone();
    let message_http = http_client.clone();

    let bot = Bot::builder()
        .with_backend(backend)
        .skip_history_sync()
        .with_event_delivery(EventDelivery::Ordered { capacity: 256 })
        .on_qr_code(move |code, _timeout| {
            let pairing = pairing_qr.clone();
            async move {
                let text = code.to_string();
                match qr_ascii(&text) {
                    Ok(ascii) => println!("{ascii}"),
                    Err(_) => println!("QR recebido. Abra /pair para a imagem."),
                }
                pairing.set_qr(text);
            }
        })
        .on_event(move |event, _client| {
            let pairing = pairing_events.clone();
            async move {
                if matches!(&*event, Event::Connected(_)) {
                    pairing.mark_connected();
                    tracing::info!("conectado ao WhatsApp");
                }
            }
        })
        .on_message(move |ctx| {
            let db = message_db.clone();
            let cfg = message_cfg.clone();
            let http_client = message_http.clone();
            async move {
                if ctx.info.source.is_from_me
                    || ctx.info.source.chat.is_group()
                    || ctx.info.source.chat.is_broadcast_list()
                    || ctx.info.source.chat.is_status_broadcast()
                {
                    return;
                }
                let chat = ctx.info.source.chat.clone();
                let jid = chat.to_string();
                let audio = ctx.message.get_base_message().audio_message.as_option();
                let body = ctx.message.text_content().map(str::to_string);
                if body.is_none() && audio.is_none() {
                    return;
                }
                let chat_id = match db.ensure_whatsapp_user(&jid).await {
                    Ok(chat_id) => chat_id,
                    Err(error) => {
                        tracing::error!(%error, "ensure user");
                        let _ = ctx.reply("Não consegui acessar o radar agora.").await;
                        return;
                    }
                };
                let result = if let Some(body) = body {
                    if should_show_typing(&body) {
                        let _ = ctx.client.chatstate().send_composing(&chat).await;
                    }
                    handle_text(&db, &cfg, &http_client, chat_id, &body).await
                } else if let Some(audio) = audio {
                    if cfg.llm_provider != "openai" || cfg.openai_api_key.is_empty() {
                        let _ = ctx.reply("A transcrição de áudio não está habilitada agora. Envie sua solicitação por texto.").await;
                        return;
                    }
                    if audio.view_once.unwrap_or(false) {
                        let _ = ctx.reply("Não transcrevo áudios de visualização única. Envie texto ou um áudio normal.").await;
                        return;
                    }
                    let duration = audio.seconds.unwrap_or(0);
                    if duration > cfg.assistant_max_audio_seconds {
                        let _ = ctx.reply(format!("O áudio pode ter no máximo {} segundos. Envie um trecho menor.", cfg.assistant_max_audio_seconds)).await;
                        return;
                    }
                    if audio.file_length.unwrap_or(0) > cfg.assistant_max_audio_bytes as u64 {
                        let _ = ctx.reply("O arquivo de áudio é grande demais. Envie um áudio menor.").await;
                        return;
                    }
                    let ttl = Duration::from_secs((cfg.session_ttl_hours.max(1) as u64) * 3600);
                    match db.load_session(chat_id, ttl).await {
                        Ok(Some(session)) if !matches!(session.step, whatsapp_bot::session::Step::Menu | whatsapp_bot::session::Step::Intent | whatsapp_bot::session::Step::AssistantConversation) => {
                            let _ = ctx.reply("O fluxo atual precisa de respostas por texto. Seu rascunho continua salvo.").await;
                            return;
                        }
                        Err(error) => {
                            tracing::error!(%error, "verificar estado antes de transcrever");
                            let _ = ctx.reply("Não consegui validar sua conversa agora. Tente novamente.").await;
                            return;
                        }
                        _ => {}
                    }
                    match db.consume_assistant_usage(chat_id, Some(duration), &cfg).await {
                        Ok(true) => {}
                        Ok(false) => {
                            let user = db.get_user(chat_id).await.ok().flatten();
                            let pro = Db::is_pro(user.as_ref(), Utc::now());
                            let limit = if pro { cfg.assistant_pro_audio_per_day } else { cfg.assistant_free_audio_per_day };
                            let _ = ctx.reply(format!("Você atingiu o limite diário de {limit} áudios do {}. Tente novamente amanhã.", if pro { "Radar Pro" } else { "plano grátis" })).await;
                            return;
                        }
                        Err(error) => {
                            tracing::error!(%error, "reservar quota para áudio");
                            let _ = ctx.reply("Não consegui validar seu limite de áudio agora. Tente novamente.").await;
                            return;
                        }
                    }
                    let _ = ctx.client.chatstate().send_composing(&chat).await;
                    let bytes = match ctx.client.download(audio).await {
                        Ok(bytes) if bytes.len() <= cfg.assistant_max_audio_bytes => bytes,
                        Ok(_) => {
                            let _ = ctx.reply("O arquivo de áudio é grande demais. Envie um áudio menor.").await;
                            return;
                        }
                        Err(error) => {
                            tracing::warn!(%error, "download de áudio falhou");
                            let _ = ctx.reply("Não consegui baixar seu áudio agora. Tente novamente ou envie por texto.").await;
                            return;
                        }
                    };
                    let mime = audio
                        .mimetype
                        .as_deref()
                        .unwrap_or("audio/ogg")
                        .split(';')
                        .next()
                        .unwrap_or("audio/ogg")
                        .trim()
                        .to_lowercase();
                    match transcribe_audio(&http_client, &cfg, bytes, &mime).await {
                        Ok(Some(text)) => handle_transcribed_audio(
                            &db, &cfg, &http_client, chat_id, &text, duration,
                        )
                        .await,
                        Ok(None) => {
                            let _ = ctx.reply("Não consegui transcrever esse áudio. Tente novamente ou envie por texto.").await;
                            return;
                        }
                        Err(error) => {
                            tracing::warn!(%error, "transcrição WhatsApp falhou");
                            let _ = ctx.reply("Não consegui transcrever esse áudio agora. Tente novamente ou envie por texto.").await;
                            return;
                        }
                    }
                } else {
                    return;
                };
                match result {
                    Ok(messages) => {
                        let sender = WaSender::new(ctx.client.clone(), http_client);
                        if let Err(error) = sender.send_to(&jid, &messages).await {
                            tracing::error!(%error, "envio");
                        }
                    }
                    Err(error) => {
                        tracing::error!(%error, "handler");
                        let _ = ctx.reply("Não consegui acessar o radar agora.").await;
                    }
                }
                let _ = ctx.client.chatstate().send_paused(&chat).await;
            }
        })
        .build()
        .await?;

    let client = bot.client();
    let handle = bot.spawn();
    let notify_db = db.clone();
    let notify_cfg = cfg.clone();
    let notify_http = http_client.clone();
    let notify_client = client;
    let notify_task = tokio::spawn(async move {
        let sender = WaSender::new(notify_client, notify_http);
        loop {
            tokio::time::sleep(Duration::from_secs(30)).await;
            let now = now_maceio();
            if !due(now, read_stamp(&notify_cfg.notify_stamp_path)) {
                continue;
            }
            if let Err(error) = write_stamp(&notify_cfg.notify_stamp_path, now.date_naive()) {
                tracing::error!(%error, "stamp da notificação");
                continue;
            }
            tracing::info!("notificação diária");
            if let Err(error) = run_daily(&notify_db, &sender, &notify_cfg).await {
                tracing::error!(%error, "notificação");
            }
        }
    });

    wait_for_shutdown().await;
    tracing::info!("encerrando");
    handle.shutdown().await;
    notify_task.abort();
    http_task.abort();
    Ok(())
}

async fn wait_for_shutdown() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let terminate = async {
        if let Ok(mut signal) =
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        {
            signal.recv().await;
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => {}
        _ = terminate => {}
    }
}
