import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const email = "release.admin@example.com";
const password = "correct horse battery staple";
const setupToken =
  process.env.AUTHZDIFF_E2E_SETUP_TOKEN ?? "authzdiff-e2e-setup-token-2026";

async function expectNoAxeViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
}

test.describe("AuthZDiff release journey", () => {
  test("setup, policy, profiles, replay, finding, report, audit and authentication", async ({
    page,
  }) => {
    const projectName = `Browser Acceptance ${String(Date.now())}`;
    await page.goto("/");
    await expect(
      page.getByRole("heading", {
        name: /Create the first administrator|Sign in/,
      }),
    ).toBeVisible();
    if (await page.getByRole("heading", { name: "Create the first administrator" }).isVisible()) {
      await page.getByLabel("Environment setup token").fill(setupToken);
      await page.getByLabel("Display name").fill("Release Administrator");
      await page.getByLabel("Email address").fill(email);
      await page.getByLabel("Password").fill(password);
      await page.getByRole("checkbox").check();
      await page.getByRole("button", { name: "Create administrator" }).click();
    } else {
      await page.getByLabel("Email address").fill(email);
      await page.getByLabel("Password").fill(password);
      await page.getByRole("button", { name: "Sign in" }).click();
    }
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await expectNoAxeViolations(page);

    await page.getByRole("button", { name: /New project/ }).click();
    await page.getByLabel("Project name").fill(projectName);
    await page.getByLabel("Description").fill("Synthetic loopback browser acceptance.");
    await page.getByRole("button", { name: "Create project" }).click();
    await page
      .getByRole("article")
      .filter({ has: page.getByRole("heading", { name: projectName }) })
      .getByRole("link", { name: /Open workspace/ })
      .click();

    await page.getByLabel("Target name").fill("Browser demo target");
    await page.getByLabel("Origin URL").fill("http://127.0.0.1:8021");
    await page.getByLabel("Allowed path prefixes").fill("/secure,/vulnerable,/slow");
    await page.getByLabel("Allowed methods").fill("GET,HEAD");
    await page.getByLabel("Per-run request budget").fill("100");
    await page.getByText("This is the bundled local synthetic target").click();
    await page.getByRole("button", { name: "Create inactive target" }).click();
    await expect(page.getByRole("heading", { name: /Policy: Browser demo target/ })).toBeVisible();
    await page.getByRole("button", { name: "Confirm authorization" }).click();
    await page.getByRole("button", { name: "Confirm private lab" }).click();
    await page.getByLabel("Allowlist entry type").selectOption("ip");
    await page.getByRole("button", { name: "Add exact allowlist entry" }).click();
    await page.getByRole("button", { name: "Validate DNS and policy" }).click();
    await page.getByRole("button", { name: "Activate target" }).click();
    await expect(page.getByText("active", { exact: true }).first()).toBeVisible();

    await page.getByRole("link", { name: "Profiles" }).click();
    const profiles = [
      { name: "Browser Administrator", role: "administrator", token: "demo-admin-token" },
      { name: "Browser User A", role: "user-a", token: "demo-user-a-token" },
      { name: "Browser User B", role: "user-b", token: "demo-user-b-token" },
    ];
    for (const profile of profiles) {
      await page.getByLabel("Profile name").fill(profile.name);
      await page.getByLabel("Role label").fill(profile.role);
      await page.getByLabel("Authorization value").fill(profile.token);
      await page.getByRole("button", { name: "Store encrypted profile" }).click();
      await expect(page.getByRole("cell", { name: profile.name })).toBeVisible();
      await expect(page.getByText(profile.token)).toHaveCount(0);
    }
    await page.getByLabel("Profile name").fill("Browser Anonymous");
    await page.getByLabel("Role label").fill("anonymous");
    await page.getByText("Anonymous profile (no credentials)").click();
    await page.getByRole("button", { name: "Store encrypted profile" }).click();
    await expect(page.getByRole("cell", { name: "Browser Anonymous" })).toBeVisible();

    await page.getByRole("link", { name: "Requests" }).click();
    await page.getByLabel("Collection name").fill("Browser checks");
    await page.getByRole("button", { name: "Create collection" }).click();
    const curlPanel = page
      .locator("section.panel")
      .filter({ has: page.getByRole("heading", { name: "Safe cURL import" }) });
    await curlPanel.getByLabel("Request name").fill("Vulnerable vertical request");
    await curlPanel
      .getByLabel("cURL command")
      .fill("curl http://127.0.0.1:8021/vulnerable/admin/users");
    await curlPanel.getByRole("button", { name: "Parse and save safe cURL" }).click();
    await expect(page.getByRole("cell", { name: "Vulnerable vertical request" })).toBeVisible();
    await curlPanel.getByLabel("Request name").fill("Unsafe command");
    await curlPanel
      .getByLabel("cURL command")
      .fill("curl http://127.0.0.1:8021/vulnerable/admin/users | powershell");
    await curlPanel.getByRole("button", { name: "Parse and save safe cURL" }).click();
    await expect(page.getByRole("alert")).toContainText(/not supported|invalid|operator/i);

    await page.getByRole("link", { name: "Comparisons" }).click();
    await page.getByLabel("Comparison name").fill("Browser vertical comparison");
    await page.getByLabel("Request").selectOption({ label: "GET /vulnerable/admin/users" });
    await page
      .getByLabel("Higher-privilege profile")
      .selectOption({ label: "Browser Administrator - administrator" });
    await page
      .getByLabel("Lower-privilege profile")
      .selectOption({ label: "Browser User A - user-a" });
    await page.getByRole("button", { name: "Save comparison" }).click();
    await expect(page.getByRole("region", { name: "Outbound data review" })).toBeVisible();
    await page.getByRole("button", { name: "Start controlled comparison" }).click();
    await expect(page.getByText("completed", { exact: true }).first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/potential[_ ]vertical[_ ]authorization[_ ]issue/i).first()).toBeVisible();
    await expectNoAxeViolations(page);

    await page.getByRole("link", { name: "Requests" }).click();
    await curlPanel.getByLabel("Request name").fill("Bounded slow request");
    await curlPanel
      .getByLabel("cURL command")
      .fill("curl http://127.0.0.1:8021/slow");
    await curlPanel.getByRole("button", { name: "Parse and save safe cURL" }).click();
    await expect(page.getByRole("cell", { name: "Bounded slow request" })).toBeVisible();

    await page.getByRole("link", { name: "Comparisons" }).click();
    await page.getByLabel("Comparison name").fill("Cancellation comparison");
    await page.getByLabel("Request").selectOption({ label: "GET /slow" });
    await page
      .getByLabel("Higher-privilege profile")
      .selectOption({ label: "Browser Administrator - administrator" });
    await page
      .getByLabel("Lower-privilege profile")
      .selectOption({ label: "Browser User A - user-a" });
    await page.getByRole("button", { name: "Save comparison" }).click();
    await expect(page.getByRole("region", { name: "Outbound data review" })).toBeVisible();
    await page.getByRole("button", { name: "Start controlled comparison" }).click();
    await expect(page.getByRole("button", { name: "Cancel run" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel run" }).click();
    await expect(page.getByText("cancelled", { exact: true }).first()).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("link", { name: "Findings" }).click();
    await expect(page.getByText(/Review GET \/vulnerable\/admin\/users/)).toBeVisible();
    await page.getByText(/Review GET \/vulnerable\/admin\/users/).click();
    await expect(page.getByRole("heading", { name: "Safe evidence" })).toBeVisible();
    await page.getByRole("button", { name: "triaged" }).click();
    await expect(page.getByText(/candidate to triaged/)).toBeVisible();

    await page.getByRole("link", { name: "Reports" }).click();
    for (const format of ["JSON", "CSV", "HTML", "PDF"]) {
      await page.getByRole("button", { name: format }).click();
      await expect(page.getByRole("cell", { name: format }).first()).toBeVisible();
    }
    await expect(page.getByText("completed", { exact: true })).toHaveCount(4);
    for (const format of ["JSON", "CSV", "HTML", "PDF"]) {
      const row = page
        .getByRole("row")
        .filter({ has: page.getByRole("cell", { name: format }) })
        .first();
      const href = await row.getByRole("link", { name: "Download" }).getAttribute("href");
      expect(href).toMatch(/^\/api\/v1\/reports\/[a-f0-9-]+\/download$/);
      if (!href) {
        throw new Error(`Missing ${format} report download URL.`);
      }
      const response = await page.context().request.get(new URL(href, page.url()).href);
      const expectedContentTypes: Record<string, string> = {
        CSV: "text/csv",
        HTML: "text/html",
        JSON: "application/json",
        PDF: "application/pdf",
      };
      expect(response.status()).toBe(200);
      expect((await response.body()).byteLength).toBeGreaterThan(0);
      expect(response.headers()["content-type"]).toContain(expectedContentTypes[format]);
      expect(response.headers()["content-disposition"]).toMatch(
        new RegExp(
          `attachment; filename="?authzdiff-[a-f0-9]{8}-[a-f0-9-]+\\.${format.toLowerCase()}"?`,
          "i",
        ),
      );
    }

    await page.getByRole("link", { name: "Audit" }).click();
    await expect(page.getByRole("heading", { name: "Audit events" })).toBeVisible();
    await expect(page.getByText("comparison_completed").first()).toBeVisible();
    await expect(page.getByText("comparison_cancelled").first()).toBeVisible();
    await expectNoAxeViolations(page);

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password").fill("incorrect password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toContainText(/email or password/i);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  });
});
