use std::io::Cursor;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use image::{ImageFormat, Luma};
use qrcode::QrCode;

#[derive(Debug, Default)]
pub struct Pairing {
    pub qr: Mutex<Option<String>>,
    pub connected: AtomicBool,
}

impl Pairing {
    pub fn set_qr(&self, code: impl Into<String>) {
        *self.qr.lock().expect("qr lock") = Some(code.into());
        self.connected.store(false, Ordering::SeqCst);
    }

    pub fn mark_connected(&self) {
        self.connected.store(true, Ordering::SeqCst);
        *self.qr.lock().expect("qr lock") = None;
    }

    pub fn qr(&self) -> Option<String> {
        self.qr.lock().expect("qr lock").clone()
    }

    pub fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }
}

pub fn qr_png(data: &str) -> anyhow::Result<Vec<u8>> {
    let code = QrCode::new(data.as_bytes())?;
    let image = code
        .render::<Luma<u8>>()
        .min_dimensions(320, 320)
        .build();
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
