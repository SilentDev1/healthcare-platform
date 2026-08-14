import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
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
      screen.getByText("Choose a procedure to compare published hospital prices."),
    ).toBeInTheDocument();
    expect(screen.queryByText("laboratory")).not.toBeInTheDocument();
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
