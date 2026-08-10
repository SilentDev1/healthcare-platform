import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import type { FacilityProcedureOverviewItem } from "../../lib/api";
import { FacilityPrices } from "./FacilityPrices";

const price = (id: string, name: string): FacilityProcedureOverviewItem => ({
  facility_location_id: "location-1",
  location_name: "Main campus",
  city: "Concord",
  procedure_slug: id,
  procedure_name: name,
  service_settings: ["outpatient"],
  cash_price_min: "100",
  cash_price_max: "100",
  negotiated_price_min: null,
  negotiated_price_max: null,
  source_url: "https://example.test/prices.csv",
  latest_updated: "2026-08-01T12:00:00Z",
  summary_count: 3,
});

describe("FacilityPrices", () => {
  it("filters published procedures without inventing empty results", () => {
    render(
      <FacilityPrices
        items={[price("mri", "MRI brain"), price("ct", "CT chest")]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Search available procedures"), {
      target: { value: "MRI" },
    });
    expect(screen.getByText("MRI brain")).toBeInTheDocument();
    expect(screen.queryByText("CT chest")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search available procedures"), {
      target: { value: "colonoscopy" },
    });
    expect(
      screen.getByText(/No published procedures match/),
    ).toBeInTheDocument();
  });
});
