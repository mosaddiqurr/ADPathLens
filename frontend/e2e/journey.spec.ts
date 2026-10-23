import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
async function accessible(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  expect(
    result.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact ?? ""),
    ),
  ).toEqual([]);
}
async function noOverflow(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
}
test("local demo to evidence, graph, remediation, exports, and persisted results", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Find the path/ }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Primary navigation" })
      .getByRole("link"),
  ).toHaveCount(4);
  await page.screenshot({ path: "test-results/ui-home.png", fullPage: true });
  await accessible(page);
  await page.getByRole("link", { name: "Load demo", exact: true }).click();
  await expect(page.getByText("Directory data loaded")).toBeVisible();
  await expect(page.getByLabel("Privileged target")).toContainText(
    "Domain Admins",
  );
  await page.screenshot({
    path: "test-results/ui-analyze.png",
    fullPage: true,
  });
  await accessible(page);
  await page.getByRole("button", { name: "Run analysis", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Results", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Inspect path from/ }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Why this matters" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Break this path" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Interactive privilege relationship graph" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/ui-results.png",
    fullPage: true,
  });
  await accessible(page);
  await page.getByText("Source evidence", { exact: true }).first().click();
  await expect(
    page.getByText(/Synthetic ADPathLens lab/).first(),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Inspect path from Mina Rahman to Domain Admins",
      exact: true,
    })
    .click();
  await page
    .getByRole("region", { name: "Focused path exploration" })
    .screenshot({ path: "test-results/ui-graph-long-path.png" });
  await page.getByText("Source evidence", { exact: true }).first().click();
  await page.screenshot({
    path: "test-results/ui-selected-path.png",
    fullPage: true,
  });
  const graphCanvas = page.getByRole("img", {
    name: "Interactive privilege relationship graph",
  });
  await graphCanvas.scrollIntoViewIfNeeded();
  const graphBounds = await graphCanvas.boundingBox();
  expect(graphBounds).not.toBeNull();
  const beforePan = await graphCanvas.screenshot();
  await page.mouse.move(
    graphBounds!.x + graphBounds!.width - 30,
    graphBounds!.y + graphBounds!.height - 25,
  );
  await page.mouse.down();
  await page.mouse.move(
    graphBounds!.x + graphBounds!.width - 90,
    graphBounds!.y + graphBounds!.height - 50,
    { steps: 8 },
  );
  await page.mouse.up();
  expect((await graphCanvas.screenshot()).equals(beforePan)).toBe(false);
  const beforeZoom = await graphCanvas.screenshot();
  await page.getByRole("button", { name: "Zoom in" }).click();
  expect((await graphCanvas.screenshot()).equals(beforeZoom)).toBe(false);
  await page.getByRole("button", { name: "Zoom out" }).click();
  await page.getByRole("button", { name: "Show nearby relationships" }).click();
  await expect(
    page.getByText("Path and nearby relationships", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Loading nearby relationships…")).toHaveCount(0);
  await page.getByRole("button", { name: "Fit graph" }).click();
  await page
    .getByRole("region", { name: "Focused path exploration" })
    .screenshot({ path: "test-results/ui-graph.png" });
  await page.getByRole("button", { name: "Path only", exact: true }).click();
  await page.getByLabel("Entity name").fill("no-such-entity");
  await expect(
    page.getByRole("heading", { name: "No paths match these filters" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/ui-filter-empty.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page
    .getByRole("combobox", { name: "Severity", exact: true })
    .selectOption("high");
  await expect(
    page.getByRole("button", { name: /Inspect path from/ }).first(),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Severity", exact: true })
    .selectOption("");
  for (const format of ["pdf", "json"]) {
    await page.getByLabel("Report format").selectOption(format);
    await page
      .getByRole("button", { name: "Export report", exact: true })
      .click();
    const link = page.getByRole("link", {
      name: `Download ${format.toUpperCase()} report`,
    });
    await expect(link).toBeVisible();
    const download = page.waitForEvent("download");
    await link.click();
    const file = await download;
    expect(file.suggestedFilename()).toMatch(new RegExp(`\\.${format}$`));
    await file.saveAs(`test-results/demo-report.${format}`);
  }
  const count = await page
    .getByRole("button", { name: /Inspect path from/ })
    .count();
  await page.reload();
  await expect(
    page.getByRole("button", { name: /Inspect path from/ }),
  ).toHaveCount(count);
  for (const width of [1440, 1366, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await noOverflow(page);
    await page.screenshot({
      path: `test-results/ui-results-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("navigation", { name: "Primary navigation" })
    .getByRole("link", { name: "About", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "About ADPathLens" }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/ui-about.png", fullPage: true });
  await accessible(page);
  expect(errors).toEqual([]);
});
test("import errors, loading, and analysis failures are actionable", async ({
  page,
}) => {
  await page.goto("/analyze?demo=1");
  await expect(page.getByText("Directory data loaded")).toBeVisible();
  await page.getByRole("button", { name: "Import new data" }).click();
  await page.getByLabel("JSON dataset", { exact: true }).setInputFiles({
    name: "invalid.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"nodes":"invalid"}'),
  });
  await page.getByRole("button", { name: "Validate dataset" }).click();
  await expect(
    page.getByText(/needs correction|has errors|must be|invalid/i).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/ui-import-error.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Use current snapshot" }).click();
  await expect(page.getByText("Directory data loaded")).toBeVisible();
  let releaseFailure!: () => void;
  const failureGate = new Promise<void>((resolve) => {
    releaseFailure = resolve;
  });
  await page.route("**/api/v1/snapshots/*/analyses", async (route) => {
    if (route.request().method() === "POST") {
      await failureGate;
      await route.fulfill({
        status: 503,
        contentType: "application/problem+json",
        json: {
          title: "Unavailable",
          detail: "Analysis is temporarily unavailable. Try again.",
          status: 503,
        },
      });
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Run analysis" }).click();
  await expect(
    page.getByRole("button", { name: "Analyzing directory…" }),
  ).toBeDisabled();
  await page.screenshot({
    path: "test-results/ui-analysis-loading.png",
    fullPage: true,
  });
  releaseFailure();
  await expect(page.getByRole("alert")).toContainText(
    "Analysis is temporarily unavailable",
  );
  await page.screenshot({
    path: "test-results/ui-analysis-error.png",
    fullPage: true,
  });
  await page.unroute("**/api/v1/snapshots/*/analyses");
  await page.getByRole("button", { name: "Run analysis" }).click();
  await expect(
    page.getByRole("heading", { name: "Results", exact: true }),
  ).toBeVisible();
  await page.goto("/analyze");
  await expect(page.getByText("Directory data loaded")).toBeVisible();
  await page.getByRole("button", { name: "Import new data" }).click();
  await page
    .getByLabel("JSON dataset", { exact: true })
    .setInputFiles("public/northbridge-demo.json");
  await page.getByRole("button", { name: "Validate dataset" }).click();
  await expect(page.getByText(/Ready to load/)).toBeVisible();
  const importButton = page.getByRole("button", {
    name: "Import dataset",
    exact: true,
  });
  await expect(importButton).toBeDisabled();
  await page
    .getByRole("checkbox", { name: /Authorized-use confirmation/ })
    .check();
  for (const checkbox of await page
    .getByRole("checkbox", { name: "Acknowledge", exact: true })
    .all())
    await checkbox.check();
  await importButton.click();
  await expect(page.getByText("Directory data loaded")).toBeVisible();
  await expect(page.getByLabel("Data collection")).toContainText(
    "Imported directory",
  );
  await page.getByRole("button", { name: "Run analysis", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Inspect path from/ }).first(),
  ).toBeVisible();
});
