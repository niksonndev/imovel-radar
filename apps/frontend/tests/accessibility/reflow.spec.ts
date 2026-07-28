import { test, expect } from "@playwright/test";

test.describe("WCAG 2.2 AA — Reflow (zoom 200%)", () => {
  test("não deve haver overflow horizontal em viewport 640x480", async ({ page }) => {
    // Simula zoom de 200% reduzindo viewport para largura equivalente
    await page.setViewportSize({ width: 640, height: 480 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Verifica overflow horizontal no <html> (documentElement)
    const htmlOverflow = await page.evaluate(() => {
      const el = document.documentElement;
      return {
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        overflowX: getComputedStyle(el).overflowX,
      };
    });

    // Verifica overflow horizontal no <body>
    const bodyOverflow = await page.evaluate(() => {
      const el = document.body;
      return {
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        overflowX: getComputedStyle(el).overflowX,
      };
    });

    const failures: string[] = [];

    // Só considera overflow se o estilo não for intencionalmente scroll/auto
    if (
      htmlOverflow.scrollWidth > htmlOverflow.clientWidth &&
      htmlOverflow.overflowX !== "auto" &&
      htmlOverflow.overflowX !== "scroll"
    ) {
      failures.push(
        `<html> overflow: scrollWidth=${htmlOverflow.scrollWidth} > clientWidth=${htmlOverflow.clientWidth} (overflow-x: ${htmlOverflow.overflowX})`
      );
    }

    if (
      bodyOverflow.scrollWidth > bodyOverflow.clientWidth &&
      bodyOverflow.overflowX !== "auto" &&
      bodyOverflow.overflowX !== "scroll"
    ) {
      failures.push(
        `<body> overflow: scrollWidth=${bodyOverflow.scrollWidth} > clientWidth=${bodyOverflow.clientWidth} (overflow-x: ${bodyOverflow.overflowX})`
      );
    }

    expect(failures, `Overflow horizontal detectado em viewport 640x480:\n${failures.join("\n")}`).toHaveLength(0);
  });
});