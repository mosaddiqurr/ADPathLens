import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.describe("mobile acceptance", () => {
  test("login and core project navigation remain usable without horizontal page overflow", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByLabel("Email address").fill("release.admin@example.com");
    await page.getByLabel("Password").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await page.getByRole("link", { name: /Open workspace/ }).first().click();
    await expect(page.getByRole("heading", { name: /Browser Acceptance/ }).first()).toBeVisible();
    for (const section of ["Profiles", "Requests", "Comparisons", "Findings", "Reports"]) {
      await page.getByRole("link", { name: section }).click();
      await expect(page.locator("main")).toBeVisible();
    }
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    const accessibility = await new AxeBuilder({ page }).analyze();
    expect(accessibility.violations, JSON.stringify(accessibility.violations, null, 2)).toEqual([]);
  });
});
