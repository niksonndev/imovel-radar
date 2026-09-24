use std::sync::Arc;
use std::time::Duration;

use whatsapp_bot::config::{ensure_parent_dir, Config};
use whatsapp_bot::db::Db;
use whatsapp_bot::handlers::{handle_text, should_show_typing};
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
                let Some(body) = ctx.message.text_content() else {
                    return;
                };
                let body = body.to_string();
                let chat = ctx.info.source.chat.clone();
                let jid = chat.to_string();
                if should_show_typing(&body) {
                    let _ = ctx.client.chatstate().send_composing(&chat).await;
                }
                let chat_id = match db.ensure_whatsapp_user(&jid).await {
                    Ok(chat_id) => chat_id,
                    Err(error) => {
                        tracing::error!(%error, "ensure user");
                        let _ = ctx.reply("Não consegui acessar o radar agora.").await;
                        return;
                    }
                };
                match handle_text(&db, &cfg, &http_client, chat_id, &body).await {
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
