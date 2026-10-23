import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("mobile workflow and all major screens at requested viewport widths", async ({
  page,
}) => {
  await page.goto("/analyze?demo=1");
  await expect(page.getByText("Directory data loaded")).toBeVisible();
  await page.getByRole("button", { name: "Run analysis" }).click();
  await expect(
    page.getByRole("heading", { name: "Results", exact: true }),
  ).toBeVisible();
  for (const width of [1440, 1366, 768, 390]) {
    await page.setViewportSize({ width, height: width < 700 ? 844 : 1000 });
    for (const [url, heading] of [
      ["/", /Find the path/],
      ["/analyze", "Analyze"],
      ["/results", "Results"],
      ["/about", "About ADPathLens"],
    ] as const) {
      await page.goto(url);
      await expect(
        page.getByRole("heading", {
          name: heading,
          exact: typeof heading === "string",
        }),
      ).toBeVisible();
      if (url === "/results")
        await expect(
          page.getByRole("button", { name: /Inspect path from/ }).first(),
        ).toBeVisible();
      if (url === "/analyze")
        await expect(page.getByText("Directory data loaded")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      const alignment = await page.locator(".page").evaluate((el) => {
        const box = el.getBoundingClientRect();
        return Math.abs(box.left - (window.innerWidth - box.right));
      });
      expect(alignment).toBeLessThanOrEqual(2);
      if (width === 390) {
        await page.screenshot({
          path: `test-results/ui-mobile-${url === "/" ? "home" : url.slice(1)}.png`,
          fullPage: true,
        });
        const axe = await new AxeBuilder({ page }).analyze();
        expect(
          axe.violations.filter((v) =>
            ["serious", "critical"].includes(v.impact ?? ""),
          ),
        ).toEqual([]);
      }
    }
  }
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation", { name: "Primary navigation" })
    .getByRole("link", { name: "Results", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Results", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Inspect path from/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Path details & evidence" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeVisible();
});
