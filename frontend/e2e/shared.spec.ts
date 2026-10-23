import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("built assets support shared sign-in, packaged demo, and protected report download", async ({
  page,
}) => {
  await page.goto("/analyze?demo=1");
  const external = process.env.ADPATHLENS_EXTERNAL_E2E === "1";
  await expect(
    page.getByRole("heading", {
      name: external ? "Sign in" : "Create administrator",
      exact: true,
    }),
  ).toBeVisible();
  if (!external) {
    await page.getByLabel("Display name").fill("Deployment analyst");
    await page
      .getByLabel("Email", { exact: true })
      .fill("deployment@example.com");
    await page
      .getByLabel("Password", { exact: true })
      .fill("Shared-Workflow-Regression-2026!");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Create secure workspace" }).click();
  } else {
    await page
      .getByLabel("Email", { exact: true })
      .fill("deployment@example.com");
    await page.getByLabel("Password", { exact: true }).fill("Wrong-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByText("Email or password is incorrect."),
    ).toBeVisible();
    await page
      .getByLabel("Password", { exact: true })
      .fill("Shared-Workflow-Regression-2026!");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
  }
  await page.getByRole("link", { name: "Load demo", exact: true }).click();
  await expect(page.getByText("Directory data loaded")).toBeVisible();
  await page.getByRole("button", { name: "Run analysis", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Inspect path from/ }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Inspect path from/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Why this matters" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Break this path" }),
  ).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
  await page.getByLabel("Report format").selectOption("json");
  await page
    .getByRole("button", { name: "Export report", exact: true })
    .click();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download JSON report" }).click();
  expect((await downloadEvent).suggestedFilename()).toMatch(/\.json$/);
  for (const asset of ["/logo.png", "/northbridge-demo.json"]) {
    const response = await page.request.get(asset);
    expect(response.ok()).toBe(true);
    expect(response.headers()["content-type"]).not.toContain("text/html");
  }
  await page.reload();
  await expect(
    page.getByRole("button", { name: /Inspect path from/ }).first(),
  ).toBeVisible();
  if (external) {
    const cookies = await page
      .context()
      .cookies(process.env.ADPATHLENS_E2E_API_URL);
    const session = cookies.find(
      (cookie) => cookie.name === "adpathlens_session",
    );
    expect(session).toMatchObject({
      secure: true,
      httpOnly: true,
      sameSite: "Lax",
    });
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Sign in", exact: true }),
    ).toBeVisible();
    const invalidSession = await page.request.get(
      `${process.env.ADPATHLENS_E2E_API_URL}/api/v1/auth/me`,
    );
    expect(invalidSession.status()).toBe(401);
    await page
      .getByLabel("Email", { exact: true })
      .fill("deployment@example.com");
    await page
      .getByLabel("Password", { exact: true })
      .fill("Shared-Workflow-Regression-2026!");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: /Find the path/ }),
    ).toBeVisible();
    await page.goto("/results");
    await expect(
      page.getByRole("button", { name: /Inspect path from/ }).first(),
    ).toBeVisible();
  }
});
