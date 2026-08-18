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
  cash_price_value_count: 1,
  matching_negotiated_rate_count: 3,
  distinct_payer_count: 1,
  distinct_plan_count: 2,
  published_payers: [
    {
      slug: "example",
      name: "Example Insurance",
      rate_count: 3,
      plan_count: 2,
    },
  ],
  all_published_negotiated_min: "640",
  all_published_negotiated_max: "1110",
  data_completeness: "high_data_completeness",
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
    // Truthful insurance availability — never "insurance accepted".
    expect(screen.getByText("1 company publishes rates")).toBeInTheDocument();
    // CMS quality, not fabricated review stars.
    expect(screen.getByText(/4\/5 CMS/)).toBeInTheDocument();
    expect(
      screen.getByText("Price details", { selector: "summary" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/insurance accepted/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View price details" }),
    ).toBeInTheDocument();

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
      screen.getByText("No published price available for this procedure"),
    ).toBeInTheDocument();
    expect(screen.getByText(/currently publishable price/)).toBeInTheDocument();
  });

  it("prioritizes only explicitly selected insurance rates", () => {
    render(
      <ComparisonFacilityCard
        item={baseItem}
        procedureName="MRI brain"
        procedureSlug="mri-brain"
        payerName="Example Insurance"
      />,
    );
    // The selected payer's published rate is shown by name (not "accepted").
    expect(screen.getByText("Example Insurance")).toBeInTheDocument();
    expect(screen.getAllByText(/\$640/).length).toBeGreaterThan(0);
    expect(screen.queryByText("$825")).not.toBeInTheDocument();
    expect(
      screen.getByText(/3 matching published rate records/),
    ).toBeInTheDocument();
  });

  it("shows distance and deterministic comparable-cash insights", () => {
    render(
      <ComparisonFacilityCard
        item={{
          ...baseItem,
          distance_miles: 8.4,
          is_lowest_comparable_cash: false,
          published_price_difference: "236",
          lower_priced_nearby_option: {
            facility_id: "f2",
            facility_name: "Lower Hospital",
            facility_location_id: "l2",
            comparable_cash_price: "589",
            published_price_difference: "236",
            distance_miles: 11.2,
          },
        }}
        procedureName="MRI knee"
        procedureSlug="mri-knee"
      />,
    );
    // Natural-language nearby savings: "↓ $236 lower published price nearby · Lower Hospital · 11.2 miles"
    expect(
      screen.getByText(/lower published price nearby/),
    ).toBeInTheDocument();
    expect(screen.getByText(/\$236/)).toBeInTheDocument();
    expect(screen.getByText(/Lower Hospital/)).toBeInTheDocument();
    expect(screen.getByText(/11\.2 miles/)).toBeInTheDocument();
    // No raw +/- difference badge is shown to consumers.
    expect(screen.queryByText(/\+\$236/)).not.toBeInTheDocument();
  });

  it("labels the lowest comparable cash price and never invents savings for ranges", () => {
    const { rerender } = render(
      <ComparisonFacilityCard
        item={{ ...baseItem, is_lowest_comparable_cash: true }}
        procedureName="MRI knee"
        procedureSlug="mri-knee"
      />,
    );
    expect(
      screen.getByText("Lowest comparable published price nearby"),
    ).toBeInTheDocument();
    rerender(
      <ComparisonFacilityCard
        item={{
          ...baseItem,
          cash_price_min: "350",
          cash_price_max: "428",
          is_lowest_comparable_cash: false,
          published_price_difference: null,
        }}
        procedureName="MRI knee"
        procedureSlug="mri-knee"
      />,
    );
    expect(
      screen.queryByText("Lowest comparable published price nearby"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/lower published price nearby/),
    ).not.toBeInTheDocument();
  });

  it("renders coverage and expandable billing disclosures", () => {
    render(
      <>
        <CoverageNotice>Prices are available at 5 facilities.</CoverageNotice>
        <PricingDisclaimer />
        <PriceRange min={null} max={null} />
      </>,
    );
    expect(screen.getByText("Price coverage")).toBeInTheDocument();
    expect(screen.getByText("Important price information")).toBeInTheDocument();
    expect(screen.getByText(/Your final bill may differ/)).toBeInTheDocument();
    expect(
      screen.getByText("Price not currently available"),
    ).toBeInTheDocument();
  });
});
