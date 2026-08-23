import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({
  apiGet: vi.fn().mockResolvedValue({
    nh_facilities: 26,
    facilities_with_publishable_prices: 12,
    publishable_procedures: 48,
  }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
import Home from "./page";

describe("Home", () => {
  it("renders the New England hero with Ask Carevero primary, manual search, and coverage notice", async () => {
    render(await Home());
    // New two-column hero: left-aligned headline (title + blue accent).
    expect(
      screen.getByRole("heading", {
        name: "Find and compare healthcare prices.",
        level: 1,
      }),
    ).toBeInTheDocument();
    // Ask Carevero is the primary interaction.
    expect(screen.getByText("What are you looking for?")).toBeInTheDocument();
    // Manual search remains an obvious secondary CTA.
    expect(
      screen.getByRole("button", { name: /Search prices/ }),
    ).toBeInTheDocument();
    // New England expansion messaging (region-forward, not NH-only).
    expect(
      screen.getByText(/Carevero is expanding across New England/),
    ).toBeInTheDocument();
    // Transparent current coverage still surfaced below the hero: multi-state,
    // published-procedure count (no stale hospital ratio now that MA is live).
    expect(
      screen.getByText(
        /Live in New Hampshire and Massachusetts, with published prices for 48 procedures/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Missing data stays visibly missing/),
    ).toBeInTheDocument();
  });
});
