import { ImageResponse } from "next/og";

export const size = {
  width: 1200,
  height: 630,
};

export const dynamic = "force-static";

export const contentType = "image/png";

export const alt =
  "Imóvel Radar — anúncios novos do OLX Maceió direto no Telegram";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 32,
          background: "#111111",
          color: "#ffffff",
        }}
      >
        <div style={{ display: "flex", fontSize: 110, fontWeight: 700 }}>
          Imóvel Radar
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 42,
            color: "#4DA3D9",
          }}
        >
          Anúncios novos do OLX Maceió direto no Telegram
        </div>
      </div>
    ),
    size
  );
}
