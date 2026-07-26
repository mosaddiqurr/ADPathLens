import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const adminEmail = "admin@northbridge.example";
const adminPassword = "Correct-Horse-Battery-Staple-2604";
let projectUrl = "";

async function expectAccessible(page: import("@playwright/test").Page) {
  const result = await new AxeBuilder({ page }).analyze();
  const serious = result.violations.filter((item) =>
    ["serious", "critical"].includes(item.impact ?? ""),
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
}

test("complete defensive desktop journey persists and enforces isolation", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "ADPathLens" })).toBeVisible();
  await page.getByLabel("Display name").fill("Northbridge Administrator");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Password").fill(adminPassword);
  await page.getByLabel(/authorized-use requirement/i).check();
  await page.getByRole("button", { name: "Create secure workspace" }).click();
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel("Name").first().fill("Blue Team Workspace");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page.getByText("Workspace created.")).toBeVisible();
  await page.getByLabel("Workspace").selectOption({ label: "Blue Team Workspace" });
  await page.getByLabel("Name").last().fill("NORTHBRIDGE Assessment");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByText("Project created.")).toBeVisible();
  await page.getByRole("link", { name: /NORTHBRIDGE Assessment/ }).click();
  projectUrl = page.url();

  await page.getByRole("link", { name: "Imports" }).click();
  await page.getByLabel(/Authorized-use confirmation/).check();
  await page.getByRole("button", { name: "Import demo snapshot" }).click();
  await expect(page.getByText(/Imported Northbridge/i)).toBeVisible();
  await page.getByRole("link", { name: /Open latest graph/ }).click();
  await expect(page.getByRole("heading", { name: /Northbridge/i })).toBeVisible();
  await page.getByPlaceholder("Search names or external IDs").fill("Mina Rahman");
  await page.getByRole("button", { name: "Find" }).click();
  await expect(page.getByRole("heading", { name: "Mina Rahman" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Domain Admins");
  await expectAccessible(page);

  await page.getByRole("link", { name: "Paths" }).click();
  await expect(page.getByLabel("Source")).toContainText("Mina Rahman");
  await page.getByLabel("Relationship filter").selectOption("guided");
  await page.getByRole("button", { name: "Run bounded analysis" }).click();
  await expect(page.getByText(/Found 1 bounded possible path/)).toBeVisible();
  await expect(page.getByLabel("Path 1")).toContainText(
    "Mina RahmanMemberOfHelpdeskResetPasswordPriya NairMemberOfServer OperatorsAdminToNB-WEB-01HasSessionOmar HassanMemberOfDomain Admins",
  );
  await expect(page.getByText(/does not prove exploitation or compromise/i)).toBeVisible();
  await page.getByRole("button", { name: "Run deterministic risk scan" }).click();
  await expect(page.getByText(/draft finding/)).toBeVisible();

  await page.getByRole("link", { name: "Open findings" }).click();
  await expect(page.getByRole("table")).toContainText("high");
  await page.getByRole("link", { name: "Review evidence" }).first().click();
  await expect(page.getByRole("heading", { name: "Why this matters" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recommended remediation" })).toBeVisible();
  await page.getByLabel("New note").fill("Evidence reviewed against the fictional source.");
  await page.getByRole("button", { name: "Add note" }).click();
  await expect(page.getByText("Analyst note added.")).toBeVisible();
  await page.getByLabel("Status").selectOption("confirmed");
  await page.getByLabel("Review note").fill("Confirmed for the synthetic lab journey.");
  await page.getByRole("button", { name: "Save decision" }).click();
  await expect(page.getByText("Review decision recorded.")).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("link", { name: "Plan simulated change" }).click();
  await page.getByLabel("Plan name").fill("Remove fictional reset right");
  await page.getByRole("button", { name: "Create plan" }).click();
  await expect(page.getByText("Remediation plan created.")).toBeVisible();
  const relationshipSelect = page.getByLabel("Stored relationship");
  const resetRelationshipId = await relationshipSelect
    .locator("option", { hasText: "rel-helpdesk-priya" })
    .getAttribute("value");
  await relationshipSelect.selectOption(resetRelationshipId ?? "");
  await page.getByLabel("Typed change").selectOption("remove_password_reset");
  await page.getByRole("button", { name: "Add simulated action" }).click();
  await expect(page.getByText("Simulation action added.")).toBeVisible();
  await page.getByRole("button", { name: "Preview graph changes" }).click();
  await expect(page.getByText("Simulation preview is ready.")).toBeVisible();
  await page.getByRole("button", { name: "Create derived snapshot" }).click();
  await expect(page.getByText(/Created immutable derived snapshot/)).toBeVisible();
  await page.getByRole("button", { name: "Retest derived snapshot" }).click();
  await expect(page.getByText(/Retest completed/)).toBeVisible();
  await page.getByRole("link", { name: /Compare remediation outcome/ }).click();
  await page.getByRole("button", { name: "Compare snapshots" }).click();
  await expect(page.getByText("Stored snapshot comparison created.")).toBeVisible();
  await expect(page.getByText("rel-helpdesk-priya")).toBeVisible();

  await page.getByRole("link", { name: "Reports" }).click();
  await page.getByLabel("Content").selectOption("findings");
  await page.getByLabel("HTML").check();
  await page.getByRole("button", { name: "Generate sanitized report" }).click();
  await expect(page.getByText(/Generated adpathlens-findings/)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download" }).first().click();
  const download = await downloadPromise;
  expect(await download.suggestedFilename()).toMatch(/^adpathlens-findings-[a-f0-9]{8}\.html$/);

  await page.reload();
  await expect(page.getByRole("heading", { name: /reports/ })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("HTML");

  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Display name").fill("Unassigned Analyst");
  await page.getByLabel("Email").fill("other@northbridge.example");
  await page.getByLabel("Temporary password").fill("Other-Correct-Horse-Battery-2604");
  await page.getByLabel("Global role").selectOption("analyst");
  await page.getByRole("button", { name: "Create user" }).click();
  await expect(page.getByText("User created.")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByLabel("Email").fill("other@northbridge.example");
  await page.getByLabel("Password").fill("Other-Correct-Horse-Battery-2604");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible();
  await page.goto(projectUrl);
  await expect(page.getByText(/does not exist/)).toBeVisible();
  const projectId = new URL(projectUrl).pathname.split("/").at(-1);
  const response = await page.request.get(`/api/v1/projects/${projectId}`);
  expect(response.status()).toBe(404);
});
