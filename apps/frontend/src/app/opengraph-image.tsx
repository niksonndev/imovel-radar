import { ImageResponse } from "next/og";

import { OG_IMAGE_TAGLINE } from "@/content/page-content";
import { SITE_NAME } from "@/lib/site";

export const size = {
  width: 1200,
  height: 630,
};

export const dynamic = "force-static";

export const contentType = "image/png";

export const alt = `${SITE_NAME} — ${OG_IMAGE_TAGLINE}`;

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
          {SITE_NAME}
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 42,
            color: "#4DA3D9",
          }}
        >
          {OG_IMAGE_TAGLINE}
        </div>
      </div>
    ),
    size
  );
}
