import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import type { ProcedureComparisonItem } from "../../lib/api";
import {
  ComparisonFacilityCard,
  CoverageNotice,
  PriceRange,
  PricingDisclaimer,
} from "./ui";

afterEach(cleanup);

const baseItem: ProcedureComparisonItem = {
  facility_id: "facility-1",
  facility_name: "Example Hospital",
  facility_location_id: "location-1",
  location_name: "Downtown Campus",
  location_type: "hospital_campus",
  address_line_1: "1 Main St",
  city: "Concord",
  state: "NH",
  postal_code: "03301",
  facility_type: "Acute Care Hospital",
  cms_overall_rating: "4",
  price_available: true,
  cash_price_min: "825",
  cash_price_max: "825",
  negotiated_price_min: "640",
  negotiated_price_max: "1110",
  service_settings: ["outpatient"],
  summary_count: 5,
  source_count: 1,
  latest_updated: "2026-08-01T12:00:00Z",
  source_url: "https://hospital.example/prices.csv",
};

describe("consumer pricing components", () => {
  it("renders honest published and unavailable price states", () => {
    const { rerender } = render(
      <ComparisonFacilityCard
        item={baseItem}
        procedureName="MRI brain"
        procedureSlug="mri-brain"
      />,
    );
    expect(screen.getByText("$825")).toBeInTheDocument();
    expect(
      screen.getByText("MRI brain", { selector: ".card-procedure strong" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/\$640/)).toBeInTheDocument();
    expect(screen.getByText(/\$1,110/)).toBeInTheDocument();
    expect(screen.getByText(/Verified published source/)).toBeInTheDocument();

    rerender(
      <ComparisonFacilityCard
        procedureName="MRI brain"
        procedureSlug="mri-brain"
        item={{
          ...baseItem,
          price_available: false,
          cash_price_min: null,
          cash_price_max: null,
          negotiated_price_min: null,
          negotiated_price_max: null,
          latest_updated: null,
          source_url: null,
        }}
      />,
    );
    expect(
      screen.getByText("Price not currently available"),
    ).toBeInTheDocument();
    expect(screen.getByText(/service being unavailable/)).toBeInTheDocument();
  });

  it("renders coverage and expandable billing disclosures", () => {
    render(
      <>
        <CoverageNotice>Prices are available at 5 facilities.</CoverageNotice>
        <PricingDisclaimer />
        <PriceRange min={null} max={null} />
      </>,
    );
    expect(screen.getByText("Coverage transparency")).toBeInTheDocument();
    expect(screen.getByText("Important price information")).toBeInTheDocument();
    expect(screen.getByText(/Your final bill may differ/)).toBeInTheDocument();
    expect(
      screen.getByText("Price not currently available"),
    ).toBeInTheDocument();
  });
});
