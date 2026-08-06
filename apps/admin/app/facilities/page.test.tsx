import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../lib/api", () => ({
  apiGet: vi.fn().mockResolvedValue({
    items: [
      {
        id: "1",
        display_name: "Concord Hospital",
        city: "Concord",
        state: "NH",
        cms_certification_number: "300001",
        facility_type: "Acute Care",
        active: true,
        latest_source_name: "CMS",
        quality_measure_count: 6,
        updated_at: "2026-08-06T12:00:00Z",
      },
    ],
    total: 1,
  }),
  formatDate: () => "Aug 6, 2026",
}));

import FacilitiesPage from "./page";

describe("FacilitiesPage", () => {
  it("renders facility provenance and coverage", async () => {
    render(await FacilitiesPage());
    expect(
      screen.getByRole("link", { name: "Concord Hospital" }),
    ).toBeInTheDocument();
    expect(screen.getByText("CMS")).toBeInTheDocument();
  });
});
