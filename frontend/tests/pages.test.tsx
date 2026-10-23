import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { AppearanceProvider } from "../src/features/appearance/AppearanceContext";
import { AboutPage, HomePage } from "../src/pages/WelcomePages";

beforeEach(() => localStorage.clear());
afterEach(cleanup);

describe("public product pages", () => {
  it("offers analysis and demo entry points and explains a fictional access chain", () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: /Find the path/ }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Analyze AD data" }),
    ).toHaveAttribute("href", "/analyze");
    expect(screen.getByRole("link", { name: "Load demo" })).toHaveAttribute(
      "href",
      "/analyze?demo=1",
    );
    const chain = within(
      screen.getByLabelText("Example attack chain with fictional identities"),
    );
    expect(chain.getByText("User A")).toBeVisible();
    expect(chain.getByText("User B")).toBeVisible();
    expect(chain.getByText("Domain Admins")).toBeVisible();
  });

  it("explains the analysis limits and persists the optional accessibility preference", async () => {
    const view = () =>
      render(
        <MemoryRouter>
          <AppearanceProvider>
            <AboutPage />
          </AppearanceProvider>
        </MemoryRouter>,
      );
    view();
    expect(
      screen.getByRole("heading", { name: "Evidence before conclusions" }),
    ).toBeVisible();
    expect(
      screen.getByText(/Paths suggest possible privilege exposure/),
    ).toBeVisible();
    expect(document.documentElement).toHaveAttribute("data-motion", "full");
    const user = userEvent.setup();
    await user.click(
      screen.getByText("Accessibility preferences", { exact: true }),
    );
    await user.click(
      screen.getByLabelText("Reduce animations", { exact: true }),
    );
    expect(document.documentElement).toHaveAttribute("data-motion", "reduced");
    cleanup();
    view();
    await user.click(
      screen.getByText("Accessibility preferences", { exact: true }),
    );
    expect(
      screen.getByLabelText("Reduce animations", { exact: true }),
    ).toBeChecked();
    await user.click(
      screen.getByLabelText("Reduce animations", { exact: true }),
    );
    expect(document.documentElement).toHaveAttribute("data-motion", "full");
  });
});
