import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
const router = { replace };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams("q=lab%20tests"),
}));
vi.mock("../components/useLocale", () => ({ useLocale: () => "en" }));
vi.mock("../components/CareSearch", () => ({ CareSearch: () => <div /> }));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import SearchPage from "./page";
import { SearchCategoryResults } from "./SearchCategoryResults";

const procedures = Array.from({ length: 11 }, (_, index) => ({
  entity_type: "procedure",
  entity_id: `procedure-${index}`,
  title: index === 0 ? "Complete blood count" : `Lab procedure ${index + 1}`,
  subtitle: "Laboratory",
  location: null,
  score: 60,
  match_reason: "category_member",
  metadata: { slug: `lab-procedure-${index}`, category: "laboratory" },
}));

describe("global category search", () => {
  beforeEach(() => {
    replace.mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            items: [
              {
                entity_type: "procedure_category",
                entity_id: "category-lab",
                title: "Lab tests",
                subtitle: "Consumer laboratory procedures",
                location: null,
                score: 90,
                match_reason: "exact_category",
                metadata: {
                  slug: "laboratory",
                  procedure_count: 11,
                  navigation_only: true,
                },
              },
              ...procedures,
            ],
          }),
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders broad category navigation with canonical procedure cards", async () => {
    render(
      <SearchCategoryResults
        category={{
          entity_type: "procedure_category",
          entity_id: "category-lab",
          title: "Lab tests",
          subtitle: "Consumer laboratory procedures",
          location: null,
          score: 90,
          match_reason: "exact_category",
          metadata: {
            slug: "laboratory",
            procedure_count: 11,
            navigation_only: true,
          },
        }}
        procedures={procedures}
        locale="en"
        procedureQuery=""
      />,
    );
    expect(screen.getByText("11 procedures")).toBeInTheDocument();
    expect(screen.getByText("Lab tests")).toBeInTheDocument();
    expect(screen.getByText("Complete blood count")).toBeInTheDocument();
    expect(
      screen.getByText("Choose a procedure to compare available published prices."),
    ).toBeInTheDocument();
    expect(screen.queryByText("laboratory")).not.toBeInTheDocument();
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders one card per reported procedure (count == rendered)", async () => {
    // Resolve on a macrotask so the effect's `setTimeout(reset, 0)` (which flips
    // loading back on for a new query) fires BEFORE the response settles, matching
    // real-network ordering. An instant mock would resolve in a microtask ahead of
    // that 0ms timer and leave the UI stuck on "Searching…".
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  ok: true,
                  json: () =>
                    Promise.resolve({
                      items: [
                        {
                          entity_type: "procedure_category",
                          entity_id: "category-lab",
                          title: "Lab tests",
                          subtitle: "Consumer laboratory procedures",
                          location: null,
                          score: 90,
                          match_reason: "exact_category",
                          metadata: {
                            slug: "laboratory",
                            procedure_count: 11,
                            navigation_only: true,
                          },
                        },
                        ...procedures,
                      ],
                    }),
                }),
              20,
            ),
          ),
      ),
    );

    const { container } = render(<SearchPage />);

    // The category summary reports 11 procedures...
    expect(await screen.findByText("11 procedures", {}, { timeout: 3000 })).toBeInTheDocument();

    // ...and exactly 11 procedure cards are actually rendered underneath. This is
    // the invariant the production bug violated (count 11, cards 0): the page's
    // category-member filter must keep count and rendered results in lockstep.
    await waitFor(() => {
      expect(container.querySelectorAll(".procdir-card")).toHaveLength(11);
    });
    expect(screen.getByText("Complete blood count")).toBeInTheDocument();

    // No architecture-locked "hospital prices" wording in the category subtitle.
    expect(
      screen.getByText("Choose a procedure to compare available published prices."),
    ).toBeInTheDocument();
    // Deterministic navigation — never an LLM/price fabrication.
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
