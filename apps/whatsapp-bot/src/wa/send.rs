use std::sync::Arc;

use anyhow::Context;
use async_trait::async_trait;
use whatsapp_rust::client::Client;
use whatsapp_rust::download::MediaType;
use whatsapp_rust::media::{image_message, ImageOptions};
use whatsapp_rust::upload::UploadOptions;
use whatsapp_rust::Jid;

use crate::handlers::OutMsg;
use crate::jobs::Sender;

pub struct WaSender {
    client: Arc<Client>,
    http: reqwest::Client,
}

impl WaSender {
    pub fn new(client: Arc<Client>, http: reqwest::Client) -> Self {
        Self { client, http }
    }

    async fn send_image(&self, jid: &Jid, url: &str, caption: &str) -> anyhow::Result<()> {
        let response = self.http.get(url).send().await?;
        if !response.status().is_success() {
            anyhow::bail!("download {url} -> {}", response.status());
        }
        let bytes = response.bytes().await?;
        let upload = self
            .client
            .upload(bytes.to_vec(), MediaType::Image, UploadOptions::default())
            .await
            .context("upload da imagem")?;
        let message = image_message(
            upload,
            ImageOptions {
                caption: Some(caption.chars().take(1024).collect()),
                ..Default::default()
            },
        );
        self.client
            .send_message(jid, message)
            .await
            .context("enviar imagem")?;
        Ok(())
    }
}

#[async_trait]
impl Sender for WaSender {
    async fn send_to(&self, jid: &str, messages: &[OutMsg]) -> anyhow::Result<()> {
        let jid: Jid = jid.parse().context("jid")?;
        for message in messages {
            match message {
                OutMsg::Text(body) => {
                    self.client
                        .send_text(&jid, body)
                        .await
                        .context("enviar texto")?;
                }
                OutMsg::Image { url, caption } => {
                    if let Err(error) = self.send_image(&jid, url, caption).await {
                        tracing::warn!(%error, "foto falhou; enviando texto");
                        self.client
                            .send_text(&jid, caption)
                            .await
                            .context("enviar legenda")?;
                    }
                }
            }
        }
        Ok(())
    }
}
