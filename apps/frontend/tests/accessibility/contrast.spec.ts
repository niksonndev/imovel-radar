import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("WCAG 2.2 AA — Color Contrast", () => {
  test("não deve ter violações de contraste de cor na landing page", async ({ page }) => {
    await page.goto("/");

    // Wait for the page to be fully rendered
    await page.waitForLoadState("networkidle");

    const results = await new AxeBuilder({ page })
      .withRules(["color-contrast"])
      .analyze();

    const violations = results.violations;

    if (violations.length > 0) {
      const report = violations
        .map(
          (v) =>
            `\n❌ ${v.id} — ${v.help}\n   URL: ${v.helpUrl}\n   Impacto: ${v.impact}\n   Elementos:\n${v.nodes
              .map(
                (n) =>
                  `     - Seletor: ${n.target.join(", ")}\n       Resumo: ${(n.failureSummary ?? "").replace(/\n/g, " ").trim()}`
              )
              .join("\n")}`
        )
        .join("\n");

      expect(violations, `Violações de contraste encontradas:${report}`).toHaveLength(0);
    }
  });
});