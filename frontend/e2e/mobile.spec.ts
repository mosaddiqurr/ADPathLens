import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("mobile login and dashboard remain keyboard-accessible", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@northbridge.example");
  await page.getByLabel("Password").fill("Correct-Horse-Battery-Staple-2604");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
  const result = await new AxeBuilder({ page }).analyze();
  expect(
    result.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? "")),
  ).toEqual([]);
});
