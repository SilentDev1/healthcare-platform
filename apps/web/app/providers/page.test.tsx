import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../lib/api", () => {
  const base = {
    cms_certification_number: "301234",
    facility_type: "Acute Care Hospitals",
    organization_type: null,
    region: null,
    image_url: null,
    image_alt: null,
    image_attribution: null,
    image_source: null,
  };
  const hospital = {
    ...base,
    id: "h1",
    display_name: "Catholic Medical Center",
    city: "Manchester",
    state: "NH",
    published_procedure_count: 50,
    pricing_status: "pricing_available",
    price_available: true,
    cms_overall_rating: "4",
    organization_name: null,
    location_type: "hospital",
    capabilities: ["hospital", "emergency_department"],
  };
  const pt = {
    ...base,
    id: "l1",
    cms_certification_number: null,
    display_name: "Apple Therapy Services — Nashua",
    city: "Nashua",
    state: "NH",
    published_procedure_count: 0,
    pricing_status: "pricing_not_available_yet",
    price_available: false,
    cms_overall_rating: null,
    organization_name: "Apple Therapy Services",
    location_type: "physical_therapy",
    capabilities: ["physical_therapy"],
  };
  return {
    apiGet: vi.fn().mockResolvedValue({
      items: [hospital, pt],
      page: 1,
      page_size: 24,
      total: 2,
      total_states: 1,
      states: [{ code: "NH", name: "New Hampshire", facility_count: 2 }],
      facility_types: ["Acute Care Hospitals"],
      capabilities: [
        { capability: "hospital", location_count: 1 },
        { capability: "physical_therapy", location_count: 1 },
      ],
      regions: [],
    }),
  };
});
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import Providers from "./page";

describe("Provider directory", () => {
  it("renders provider-neutral directory with hospital-only CMS and price availability", async () => {
    render(await Providers({ searchParams: Promise.resolve({}) }));

    expect(
      screen.getByRole("heading", { name: "Find healthcare providers", level: 1 }),
    ).toBeInTheDocument();

    // Result count uses "locations", never "hospitals".
    expect(screen.getByText(/of 2 locations/)).toBeInTheDocument();

    // Capability quick-filter chips carry real counts.
    expect(
      screen.getByRole("button", { name: /Hospital \(1\)/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Physical Therapy \(1\)/ }),
    ).toBeInTheDocument();

    // CMS rating is HOSPITAL-ONLY: exactly one, and never on the PT provider.
    expect(screen.getAllByText(/CMS Overall Rating: 4\/5/)).toHaveLength(1);

    // Offered-without-price provider stays visible with the correct message.
    expect(
      screen.getByText("Published price not currently available in Carevero"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Published prices for 50 procedures"),
    ).toBeInTheDocument();

    // Provider-neutral CTA.
    expect(screen.getAllByText(/View provider/).length).toBeGreaterThanOrEqual(2);
  });
});
