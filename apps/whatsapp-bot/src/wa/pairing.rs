use std::io::Cursor;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use image::{ImageFormat, Luma};
use qrcode::QrCode;

/// Estado do pareamento, exposto para a página `/pair`.
///
/// Guardar o prazo de validade junto com o payload é o que permite a página ser
/// honesta: o WhatsApp aposenta cada QR em ~20 s e, depois de 6 refs (~160 s),
/// o cliente do `whatsapp-rust` se desconecta sozinho. Sem o prazo, a página
/// seguia exibindo o último QR (já morto) como se ainda valesse.
#[derive(Debug, Default)]
struct PairingState {
    qr: Option<String>,
    expires_at: Option<Instant>,
}

impl PairingState {
    /// QR ainda dentro da janela informada pelo servidor, com 2 s de folga para
    /// o usuário conseguir escanear antes de o WhatsApp aposentá-lo.
    fn fresh(&self) -> bool {
        match (&self.qr, self.expires_at) {
            (Some(_), Some(deadline)) => Instant::now() + Duration::from_secs(2) < deadline,
            _ => false,
        }
    }
}

#[derive(Debug, Default)]
pub struct Pairing {
    state: Mutex<PairingState>,
    connected: AtomicBool,
    exhausted: AtomicBool,
}

impl Pairing {
    /// `validity` é o prazo que o servidor deu para este QR (`timeout` do evento).
    pub fn set_qr(&self, code: impl Into<String>, validity: Duration) {
        let mut state = self.state.lock().expect("qr lock");
        state.qr = Some(code.into());
        state.expires_at = Some(Instant::now() + validity);
        drop(state);
        self.connected.store(false, Ordering::SeqCst);
        self.exhausted.store(false, Ordering::SeqCst);
    }

    /// Os QRs se esgotaram sem pareamento; o cliente se desconecta em seguida e
    /// não aceita ser reiniciado. Quem observa isso precisa subir um cliente novo.
    pub fn mark_exhausted(&self) {
        let mut state = self.state.lock().expect("qr lock");
        state.qr = None;
        state.expires_at = None;
        drop(state);
        self.exhausted.store(true, Ordering::SeqCst);
        self.connected.store(false, Ordering::SeqCst);
    }

    pub fn is_exhausted(&self) -> bool {
        self.exhausted.load(Ordering::SeqCst)
    }

    /// Payload do QR vigente — `None` quando vencido. Nunca devolver um QR morto:
    /// a página mostraria uma imagem que não pareia nada.
    pub fn fresh_qr(&self) -> Option<String> {
        let state = self.state.lock().expect("qr lock");
        if state.fresh() {
            state.qr.clone()
        } else {
            None
        }
    }

    pub fn qr_seconds_left(&self) -> Option<u64> {
        let state = self.state.lock().expect("qr lock");
        if !state.fresh() {
            return None;
        }
        state
            .expires_at
            .map(|deadline| deadline.saturating_duration_since(Instant::now()).as_secs())
    }

    pub fn mark_connected(&self) {
        self.connected.store(true, Ordering::SeqCst);
        let mut state = self.state.lock().expect("qr lock");
        state.qr = None;
        state.expires_at = None;
        drop(state);
        self.exhausted.store(false, Ordering::SeqCst);
    }

    pub fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }
}

pub fn qr_png(data: &str) -> anyhow::Result<Vec<u8>> {
    let code = QrCode::new(data.as_bytes())?;
    let image = code.render::<Luma<u8>>().min_dimensions(320, 320).build();
    let mut buffer = Cursor::new(Vec::new());
    image.write_to(&mut buffer, ImageFormat::Png)?;
    Ok(buffer.into_inner())
}

pub fn qr_ascii(data: &str) -> anyhow::Result<String> {
    let code = QrCode::new(data.as_bytes())?;
    Ok(code
        .render::<qrcode::render::unicode::Dense1x2>()
        .quiet_zone(true)
        .module_dimensions(1, 1)
        .build())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn qr_dentro_da_janela_e_servido_e_qr_vencido_nao() {
        let pairing = Pairing::default();
        pairing.set_qr("payload-1", Duration::from_secs(20));
        assert!(pairing.fresh_qr().is_some());
        assert!(pairing.qr_seconds_left().unwrap() <= 20);
        assert!(!pairing.is_exhausted());

        // O WhatsApp aposenta o QR no prazo que ele mesmo informa: depois dele a
        // página não pode continuar servindo a imagem.
        pairing.set_qr("payload-2", Duration::from_secs(1));
        assert!(pairing.fresh_qr().is_none());
        assert!(pairing.qr_seconds_left().is_none());
    }

    #[test]
    fn esgotado_limpa_o_qr_e_pareado_limpa_o_estado() {
        let pairing = Pairing::default();
        pairing.set_qr("payload", Duration::from_secs(20));
        pairing.mark_exhausted();
        assert!(pairing.is_exhausted());
        assert!(pairing.fresh_qr().is_none());
        assert!(!pairing.is_connected());

        pairing.set_qr("payload", Duration::from_secs(20));
        assert!(!pairing.is_exhausted(), "um QR novo zera o estado esgotado");

        pairing.mark_connected();
        assert!(pairing.is_connected());
        assert!(!pairing.is_exhausted());
        assert!(pairing.fresh_qr().is_none(), "pareado não mostra mais QR");
    }

    #[test]
    fn png_do_qr_e_um_png() {
        let bytes = qr_png("2@abc,def").expect("gerar png");
        assert!(bytes.starts_with(&[0x89, b'P', b'N', b'G']));
        assert!(bytes.len() > 300);
    }
}
