import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/api", () => ({
  ApiError: class ApiError extends Error {},
  apiGet: vi.fn().mockImplementation((path: string) =>
    path.endsWith("/procedure-overview")
      ? Promise.resolve({ items: [], procedure_count: 0, facility_id: "1" })
      : path.endsWith("/quality?page_size=100")
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
                id: "location-1",
                location_name: "Main campus",
                location_type: "hospital_campus",
                active: true,
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
    expect(screen.getAllByText("4/5 CMS").length).toBeGreaterThan(0);
    expect(screen.getByText(/CMS Care Compare/)).toBeInTheDocument();
    expect(
      screen.getByText(/Pricing data is not currently available/),
    ).toBeInTheDocument();
  });
});
