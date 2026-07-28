import { test, expect } from "@playwright/test";

test.describe("WCAG 2.2 AA — Navegação por Teclado", () => {
  test("navegação Tab deve alcançar todos os elementos interativos sem travamentos", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Foca o body ou primeiro elemento focável
    await page.focus("body");
    await page.keyboard.press("Tab");

    const focusOrder: string[] = [];
    const seenPaths = new Set<string>();
    const maxIterations = 100;

    for (let i = 0; i < maxIterations; i++) {
      const info = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;

        const tag = el.tagName.toLowerCase();
        const id = el.id ? `#${el.id}` : "";
        const cls = Array.from(el.classList)
          .filter((c) => !c.startsWith("focus-visible") && c !== "group/badge")
          .slice(0, 3)
          .map((c) => `.${c.replace(/:/g, "\\:")}`)
          .join("");
        const text = (el as HTMLElement).innerText?.trim().slice(0, 40) || "";

        const allElements = document.querySelectorAll("*");
        const docIndex = Array.from(allElements).indexOf(el);

        const display = `${tag}${id}${cls}${text ? ` "${text}"` : ""}`;
        return { display, path: `doc-index-${docIndex}` };
      });

      if (!info) {
        await page.keyboard.press("Tab");
        const next = await page.evaluate(() => {
          const el = document.activeElement;
          return el && el !== document.body ? "found" : null;
        });
        if (!next) break;
        continue;
      }

      if (seenPaths.has(info.path)) {
        focusOrder.push(`🔄 LOOP em: ${info.display}`);
        break;
      }

      seenPaths.add(info.path);
      focusOrder.push(info.display);

      await page.keyboard.press("Tab");
    }

    // --- Processa ordem de foco ---
    const loopLine = focusOrder.find((s) => s.startsWith("🔄 LOOP"));
    const loopDetected = !!loopLine;
    const loopIndex = loopLine ? focusOrder.indexOf(loopLine) : -1;
    const visitedBeforeLoop = focusOrder.slice(0, loopIndex >= 0 ? loopIndex : focusOrder.length);

    // --- Coleta todos os elementos interativos visíveis ---
    const interactiveSelectors = await page.evaluate(() => {
      const allElements = document.querySelectorAll<HTMLElement>(
        'a[href]:not([href=""]):not([href="#"]):not([tabindex="-1"]), ' +
        "button:not([disabled]):not([tabindex='-1']), " +
        "input:not([disabled]):not([type='hidden']):not([tabindex='-1']), " +
        "select:not([disabled]):not([tabindex='-1']), " +
        "textarea:not([disabled]):not([tabindex='-1']), " +
        "[tabindex]:not([tabindex='-1'])"
      );

      return Array.from(allElements)
        .filter((el) => {
          const style = getComputedStyle(el);
          return style.display !== "none" && style.visibility !== "hidden";
        })
        .map((el) => {
          const tag = el.tagName.toLowerCase();
          const id = el.id ? `#${el.id}` : "";
          const cls = Array.from(el.classList)
            .slice(0, 3)
            .map((c) => `.${c.replace(/:/g, "\\:")}`)
            .join("");
          const text = (el as HTMLElement).innerText?.trim().slice(0, 40) || "";
          return `${tag}${id}${cls}${text ? ` "${text}"` : ""}`;
        });
    });

    // --- Verifica se algum elemento interativo foi pulado ---
    const skipped = interactiveSelectors.filter((s) => {
      const base = s.split('"')[0].trim();
      return !visitedBeforeLoop.some((focused) => focused.includes(base));
    });

    // Loop só é problema se faltam elementos não visitados
    const prematureLoop = loopDetected && skipped.length > 0;

    // Monta relatório da ordem de foco
    const reportLines = [
      "\n=== Ordem de foco encontrada (para revisão manual) ===",
      ...visitedBeforeLoop.map((s, i) => `  ${i + 1}. ${s}`),
    ];
    if (loopDetected) {
      reportLines.push(`  (Tab wrap-around normal detectado após o último elemento)`);
    }

    const failures: string[] = [];

    if (skipped.length > 0) {
      failures.push(
        `Elementos interativos não receberam foco:\n${skipped.map((s) => `  - ${s}`).join("\n")}`
      );
    }

    if (prematureLoop) {
      failures.push("Loop infinito detectado — Tab retornou a um elemento já focado antes de percorrer todos os elementos.");
    }

    console.log(reportLines.join("\n"));

    expect(
      failures,
      `Falhas na navegação por teclado:\n${failures.join("\n\n")}\n\n${reportLines.join("\n")}`
    ).toHaveLength(0);
  });
});