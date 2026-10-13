import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";

const example = (name: string) => resolve(import.meta.dirname, "../../examples", name);
const screenshots = resolve(import.meta.dirname, "../../docs/screenshots");

async function uploadPair(page: Page, before = "snapshot-before.json", after = "snapshot-after.json") {
  await page.goto("/compare");
  await page.getByLabel("Before file", { exact: true }).setInputFiles(example(before));
  await page.getByLabel("After file", { exact: true }).setInputFiles(example(after));
  await expect(page.getByText("Ready to compare")).toHaveCount(2);
}
async function compare(page: Page) {
  await page.getByRole("button", { name: "Compare authorization", exact: true }).click();
  await expect(page.locator("#results-heading")).toBeVisible();
}
async function accessibility(page: Page) {
  const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

test("home opens directly; final upload, results, reports, and screenshots", async ({ page }, info) => {
  // Two full axe scans plus downloads need a larger total budget on emulated mobile.
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "AuthZDiff", exact: true })).toBeVisible();
  await expect(page.getByText("Sign in")).toHaveCount(0);
  await expect(page.getByRole("navigation").getByRole("link")).toHaveCount(3);
  await accessibility(page);
  if (info.project.name === "desktop" && !process.env.CI) {
    await mkdir(screenshots, { recursive: true });
    await page.screenshot({ path: resolve(screenshots, "home.png"), fullPage: true });
  }
  await page.getByRole("link", { name: "Compare access" }).click();
  if (info.project.name === "desktop" && !process.env.CI) {
    await page.screenshot({ path: resolve(screenshots, "compare.png"), fullPage: true });
  }
  await uploadPair(page);
  await compare(page);
  await expect(page.getByRole("heading", { name: "5 authorization changes" })).toBeVisible();
  const rows = page.locator(".change-row");
  await expect(rows).toHaveCount(5);
  await expect(rows.filter({ hasText: "Public" }).locator(".severity")).toHaveText("critical");
  await expect(rows.filter({ hasText: "Alice" }).locator(".state-transition")).toHaveText("Viewer→Administrator");
  await expect(rows.filter({ hasText: "Bob" }).locator(".change-badge")).toHaveText("lost");
  await accessibility(page);
  if (info.project.name === "desktop" && !process.env.CI) {
    await page.evaluate(() => { window.scrollTo(0, 0); });
    await page.screenshot({ path: resolve(screenshots, "results.png"), fullPage: true });
  }
  await rows.filter({ hasText: "Alice" }).locator("summary").first().click();
  await expect(page.getByRole("heading", { name: "Why it matters" })).toBeVisible();
  const technical = rows.filter({ hasText: "Alice" }).locator(".technical-evidence");
  await expect(technical).not.toHaveAttribute("open", "");
  await technical.locator("summary").click();
  await expect(technical.locator("pre")).toContainText('"role": "Administrator"');
  if (!process.env.CI) {
    await page.evaluate(() => { window.scrollTo({ top: 0, behavior: "instant" }); });
    await page.screenshot({ path: info.project.name === "desktop" ? resolve(screenshots, "evidence.png") : info.outputPath("mobile-evidence.png"), fullPage: true });
  }
  await page.getByRole("button", { name: "Risky", exact: true }).click();
  await expect(rows).toHaveCount(3);
  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const jsonFile = await jsonDownload;
  expect(jsonFile.suggestedFilename()).toBe("authzdiff-report.json");
  const reportPath = await jsonFile.path();
  expect(reportPath).not.toBeNull();
  const report = JSON.parse(await readFile(reportPath, "utf-8")) as { summary: { total: number }; changes: { principal: string }[] };
  expect(report.summary.total).toBe(5);
  expect(report.changes).toHaveLength(5); // Filters do not silently discard report evidence.
  const pdfDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PDF" }).click();
  const pdfFile = await pdfDownload;
  expect(pdfFile.suggestedFilename()).toBe("authzdiff-report.pdf");
  const pdfPath = await pdfFile.path();
  expect((await readFile(pdfPath)).subarray(0, 4).toString()).toBe("%PDF");
  await page.locator(".comparison-notes > summary").click();
  const csvDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV changes" }).click();
  const csvFile = await csvDownload;
  expect(csvFile.suggestedFilename()).toBe("authzdiff-report.csv");
  expect(await readFile(await csvFile.path(), "utf-8")).toContain("Alice");
  await page.getByRole("button", { name: "Clear comparison" }).click();
  await expect(page.getByRole("button", { name: "Compare authorization", exact: true })).toBeDisabled();
  await expect(rows).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("example and benign comparison; reload drops all comparison state", async ({ page }) => {
  await page.goto("/compare");
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(page.getByText("Ready to compare")).toHaveCount(2);
  await compare(page);
  await page.reload();
  await expect(page.getByText("Ready to compare")).toHaveCount(0);
  await uploadPair(page, "snapshot-before.json", "snapshot-before.csv");
  await compare(page);
  await expect(page.getByRole("heading", { name: "No authorization changes found" })).toBeVisible();
  await accessibility(page);
});

test("malformed, unsupported, incompatible inputs and safe server failures", async ({ page }) => {
  await page.goto("/compare");
  await page.getByLabel("Before file", { exact: true }).setInputFiles({ name: "bad.json", mimeType: "application/json", buffer: Buffer.from("{") });
  await expect(page.getByRole("alert")).toHaveText("The Before dataset could not be parsed.");
  await page.getByLabel("Before file", { exact: true }).setInputFiles({ name: "bad.txt", mimeType: "text/plain", buffer: Buffer.from("text") });
  await expect(page.getByRole("alert")).toHaveText("This file format is not supported.");
  await uploadPair(page, "snapshot-before.json", "capture-after.har");
  await page.getByRole("button", { name: "Compare authorization", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("The two inputs use incompatible formats.");
  await uploadPair(page);
  await page.route("**/api/v1/compare", route => route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Traceback: secret password"}' }));
  await page.getByRole("button", { name: "Compare authorization", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("The request could not be completed.");
  await expect(page.getByText("Traceback", { exact: false })).toHaveCount(0);
});

test("HAR gain and loss; malformed HAR rejected", async ({ page }) => {
  await uploadPair(page, "capture-before.har", "capture-after.har");
  await compare(page);
  await expect(page.locator(".change-row")).toHaveCount(2);
  await expect(page.locator(".change-row").filter({ hasText: "Alice" }).locator(".state-transition")).toHaveText("Denied · HTTP 403→Allowed · HTTP 200");
  await expect(page.locator(".change-row").filter({ hasText: "Bob" }).locator(".change-badge")).toHaveText("lost");
  await page.getByLabel("Before file", { exact: true }).setInputFiles({ name: "broken.har", mimeType: "application/json", buffer: Buffer.from('{"log":{"entries":[null]}}') });
  await expect(page.getByRole("alert")).toHaveText("The Before dataset could not be parsed.");
  await expect(page.getByRole("button", { name: "Compare authorization", exact: true })).toBeDisabled();
});

test("keyboard navigation, about, and creator", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeInViewport();
  await page.getByRole("link", { name: "About", exact: true }).click();
  await expect(page.getByRole("link", { name: "Mosaddiqur Rahman ↗" })).toHaveAttribute("href", "https://www.linkedin.com/in/mosaddiqur/");
  await accessibility(page);
});

test("home stays centered in the usable viewport at common widths", async ({ page }, info) => {
  test.setTimeout(120_000);
  for (const width of info.project.name === "desktop" ? [1024, 1440, 1920] : [320, 390, 760]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    const center = await page.locator(".home-intro").boundingBox();
    const usable = await page.locator(".main-area").boundingBox();
    expect(center).not.toBeNull(); expect(usable).not.toBeNull();
    if (!center || !usable) throw new Error("Home layout bounds are missing.");
    expect(Math.abs(center.x + center.width / 2 - usable.x - usable.width / 2)).toBeLessThan(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("CSV pair, redacted filenames and credentials, narrow result layout", async ({ page }, info) => {
  test.setTimeout(120_000);
  if (info.project.name === "mobile") await page.setViewportSize({ width: 320, height: 1000 });
  await page.goto("/compare");
  const before = "principal,resource,action,effect\nAlice,Billing,Read,deny";
  const after = "principal,resource,action,effect\nAlice,Billing,Read,allow";
  await page.getByLabel("Before file", { exact: true }).setInputFiles({ name: "token=tiny-secret.csv", mimeType: "text/csv", buffer: Buffer.from(before) });
  await expect(page.getByText("Ready to compare")).toHaveCount(1);
  await expect(page.locator(".upload-filename").first()).toHaveText("token=[REDACTED]");
  await expect(page.getByText("tiny-secret", { exact: false })).toHaveCount(0);
  await page.getByLabel("After file", { exact: true }).setInputFiles({ name: "after.csv", mimeType: "text/csv", buffer: Buffer.from(after) });
  await expect(page.getByText("Ready to compare")).toHaveCount(2);
  await compare(page);
  await expect(page.locator(".change-badge")).toHaveText("gained");
  await accessibility(page);
  await page.getByRole("button", { name: "Clear comparison" }).click();
  const secretBody = JSON.stringify({ apiKey: "tiny-secret", visible: "yes" });
  const har = (status: number, access: string, text: string) => JSON.stringify({ log: { entries: [{
    _authzdiff: { principal: "Alice", access }, request: { method: "GET", url: "https://example.invalid/billing" },
    response: { status, content: { mimeType: "application/json", text } },
  }] } });
  await page.getByLabel("Before file", { exact: true }).setInputFiles({ name: "before.har", mimeType: "application/json", buffer: Buffer.from(har(403, "denied", '{"message":"forbidden"}')) });
  await page.getByLabel("After file", { exact: true }).setInputFiles({ name: "after.har", mimeType: "application/json", buffer: Buffer.from(har(200, "allowed", secretBody)) });
  await expect(page.getByText("Ready to compare")).toHaveCount(2);
  await compare(page);
  await page.locator(".change-row > summary").click();
  await page.locator(".technical-evidence > summary").click();
  await expect(page.locator(".technical-evidence pre")).toContainText("[REDACTED]");
  await expect(page.getByText("tiny-secret", { exact: false })).toHaveCount(0);
  await accessibility(page);
});
