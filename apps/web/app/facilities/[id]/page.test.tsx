import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/api", () => ({
  apiGet: vi.fn().mockImplementation((path: string) =>
    path.endsWith("/quality?page_size=100")
      ? Promise.resolve({
          items: [
            {
              id: "q1",
              cms_measure_id: "OVERALL_RATING",
              measure_name: "Overall hospital rating",
              category: "overall_rating",
              score: "4",
              footnote_code: null,
            },
          ],
          total: 1,
        })
      : Promise.resolve({
          id: "1",
          display_name: "Concord Hospital",
          updated_at: "2026-08-06T12:00:00Z",
          locations: [
            {
              address_line_1: "1 Main St",
              city: "Concord",
              state: "NH",
              postal_code: "03301",
            },
          ],
        }),
  ),
}));
import FacilityPage from "./page";

describe("FacilityPage", () => {
  it("shows the CMS overall rating and attribution", async () => {
    render(await FacilityPage({ params: Promise.resolve({ id: "1" }) }));
    expect(
      screen.getByRole("heading", { name: "Concord Hospital" }),
    ).toBeInTheDocument();
    expect(screen.getByText("4 out of 5")).toBeInTheDocument();
    expect(screen.getByText(/Centers for Medicare/)).toBeInTheDocument();
  });
});
