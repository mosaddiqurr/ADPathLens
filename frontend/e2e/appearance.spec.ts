import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";

test("theme and accessibility preferences preserve analysis and remain accessible in both themes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/analyze?demo=1");
  await expect(
    page.getByText("Directory data loaded", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".workflow-steps")).toHaveCount(0);
  await expect(page.locator(".analysis-input select:visible")).toHaveCount(2);
  await expect(page.getByLabel("Maximum relationships")).toBeHidden();
  await expect(page.locator("header")).not.toContainText("Local analysis");
  await page.getByRole("button", { name: "Run analysis", exact: true }).click();
  const paths = page.getByRole("button", { name: /Inspect path from/ });
  await expect(paths.first()).toBeVisible();
  const count = await paths.count();
  await expect(page.locator(".route-content")).toHaveCSS("opacity", "1");
  const canvas = page.locator(".network-backdrop");
  await expect(page.locator("header .motion-control")).toHaveCount(0);
  await page.goto("/about");
  await page.getByText("Accessibility preferences", { exact: true }).click();
  await page.getByLabel("Reduce animations", { exact: true }).check();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(canvas).toHaveAttribute("data-animation", "static");
  const pixels = () =>
    canvas.evaluate((element) => (element as HTMLCanvasElement).toDataURL());
  const frozen = createHash("sha256")
    .update(await pixels())
    .digest("hex");
  await page
    .getByRole("heading", { name: "About ADPathLens", exact: true })
    .hover();
  expect(
    createHash("sha256")
      .update(await pixels())
      .digest("hex"),
  ).toBe(frozen);
  for (const theme of ["dark", "light"] as const) {
    if (theme === "light")
      await page
        .getByRole("button", { name: "Switch to light mode", exact: true })
        .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await page.goto("/results");
    await expect(paths).toHaveCount(count);
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
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expect(page.locator("body")).toHaveCSS(
        "color",
        theme === "light" ? "rgb(37, 38, 43)" : "rgb(239, 239, 236)",
      );
      if (url === "/results")
        await expect(
          page.getByRole("button", { name: /Inspect path from/ }).first(),
        ).toBeVisible();
      const axe = await new AxeBuilder({ page }).analyze();
      expect(
        axe.violations.filter((violation) =>
          ["serious", "critical"].includes(violation.impact ?? ""),
        ),
        `${theme} ${url}`,
      ).toEqual([]);
      await page.screenshot({
        path: `test-results/redesign-${theme}-${url === "/" ? "home" : url.slice(1)}.png`,
        fullPage: true,
        animations: "disabled",
      });
    }
  }
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await page.getByText("Accessibility preferences", { exact: true }).click();
  await page.getByLabel("Reduce animations", { exact: true }).uncheck();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator("html")).toHaveAttribute("data-motion", "full");
  await expect(page.getByRole("button", { name: /animations/i })).toHaveCount(
    0,
  );
  await page.goto("/");
  await expect(page.locator(".hero-signal")).toHaveCSS(
    "animation-name",
    "access-signal",
  );
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `overflow at ${width}px`,
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});

test("animations start by default without a header control and suspend during scrolling or offscreen", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => {
    localStorage.setItem("adpathlens.motion", "paused");
    localStorage.setItem("adpathlens.motion-preference", "off");
  });
  await page.goto("/");
  const root = page.locator("html");
  const signal = page.locator(".hero-signal");
  await expect(root).toHaveAttribute("data-motion", "full");
  await expect(page.locator("header")).not.toContainText(/Motion (on|off)/);
  await expect(page.getByRole("button", { name: /animations/i })).toHaveCount(
    0,
  );
  await expect(page.locator(".topology-chain")).toContainText("User A");
  await expect(page.locator(".topology-chain")).toContainText("User B");
  await expect(page.locator(".topology-chain")).not.toContainText(
    "Omar Hassan",
  );
  await expect(root).toHaveAttribute("data-motion", "full");
  await expect(signal).toHaveCSS("animation-name", "access-signal");
  const position = await signal.evaluate(
    (element) => getComputedStyle(element).strokeDashoffset,
  );
  await expect
    .poll(() =>
      signal.evaluate((element) => getComputedStyle(element).strokeDashoffset),
    )
    .not.toBe(position);
  await expect(page.locator(".network-backdrop")).toHaveAttribute(
    "data-animation",
    "running",
  );
  const scrolling = await page.evaluateHandle(() =>
    window.setInterval(() => scrollBy(0, 8), 30),
  );
  try {
    await expect(root).toHaveAttribute("data-scrolling", "true");
    await expect(page.locator(".network-backdrop")).toHaveAttribute(
      "data-animation",
      "suspended",
    );
  } finally {
    await scrolling.evaluate((timer) => window.clearInterval(timer));
    await scrolling.dispose();
  }
  await expect(page.locator(".network-backdrop")).toHaveAttribute(
    "data-animation",
    "running",
  );
  await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await expect
    .poll(() =>
      page
        .locator(".hero-topology")
        .evaluate((element) => element.getBoundingClientRect().bottom),
    )
    .toBeLessThanOrEqual(0);
  await expect(page.locator(".hero-topology")).toHaveAttribute(
    "data-active",
    "false",
  );
  await expect(signal).toHaveCSS("animation-play-state", "paused");
  await page.evaluate(() => scrollTo(0, 0));
  await expect(page.locator(".hero-topology")).toHaveAttribute(
    "data-active",
    "true",
  );
  await expect(signal).toHaveCSS("animation-play-state", "running");
  await page.reload();
  await expect(root).toHaveAttribute("data-motion", "full");
  await page.goto("/about");
  await page.getByText("Accessibility preferences", { exact: true }).click();
  await page.getByLabel("Reduce animations", { exact: true }).check();
  await expect(page.locator(".network-backdrop")).toHaveAttribute(
    "data-animation",
    "static",
  );
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.reload();
  await expect(root).toHaveAttribute("data-motion", "reduced");
  await page.goto("/");
  await expect(signal).toHaveCSS("animation-name", "none");
});

test("report format has room for its dropdown and stays separate from adjacent actions", async ({
  page,
}) => {
  await page.goto("/analyze?demo=1");
  await page.getByRole("button", { name: "Run analysis", exact: true }).click();
  const format = page.getByLabel("Report format", { exact: true });
  await expect(format).toBeVisible();
  for (const width of [320, 390, 768, 1242, 1440]) {
    await page.setViewportSize({ width, height: 800 });
    const selectBox = await format.boundingBox();
    const buttonBox = await page
      .getByRole("button", { name: "Export report", exact: true })
      .boundingBox();
    expect(selectBox!.width).toBeGreaterThanOrEqual(100);
    expect(
      buttonBox!.x - selectBox!.x - selectBox!.width,
    ).toBeGreaterThanOrEqual(12);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await format.selectOption("json");
    await expect(format).toHaveValue("json");
    await format.focus();
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("Enter");
    await expect(format).toHaveValue("pdf");
  }
});
