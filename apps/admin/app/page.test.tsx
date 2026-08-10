import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({
  apiGet: vi.fn().mockImplementation((path: string) => {
    if (path === "/api/v1/pricing/scorecard") {
      return Promise.reject(new Error("scorecard unavailable"));
    }
    return Promise.resolve({
      total_facilities: 28,
      nh_facilities: 28,
      latest_import_status: "COMPLETED",
      failed_import_count: 0,
      unmatched_record_count: 1,
      facilities_with_quality: 20,
      facilities_without_quality: 8,
      latest_source_downloaded_at: "2026-08-06T12:00:00Z",
    });
  }),
  formatDate: () => "Aug 6, 2026",
}));

import AdminHome from "./page";

describe("AdminHome", () => {
  it("shows operational metrics from the API", async () => {
    render(await AdminHome());
    expect(
      screen.getByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("28", { selector: "strong" })).toHaveLength(2);
    expect(screen.getByText("Unmatched records")).toBeInTheDocument();
  });
});
