import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import React, {
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

vi.mock("../../../../lib/api", () => ({
  apiGet: vi.fn().mockImplementation((path: string) => {
    if (path.includes("/comparison"))
      return Promise.resolve({
        procedure_slug: "mri-brain",
        procedure_name: "MRI brain",
        state: "NH",
        active_facilities: 26,
        facilities_with_prices: 1,
        service_locations: 2,
        items: [
          {
            facility_id: "f1",
            facility_name: "Published Hospital",
            facility_location_id: "l1",
            location_name: "Main campus",
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
            summary_count: 4,
            source_count: 1,
            latest_updated: "2026-08-01T12:00:00Z",
            source_url: "https://example.test/prices.csv",
          },
          {
            facility_id: "f2",
            facility_name: "Coverage Gap Hospital",
            facility_location_id: "l2",
            location_name: null,
            location_type: "hospital_campus",
            address_line_1: "2 Main St",
            city: "Concord",
            state: "NH",
            postal_code: "03301",
            facility_type: "Critical Access Hospital",
            cms_overall_rating: null,
            price_available: false,
            cash_price_min: null,
            cash_price_max: null,
            negotiated_price_min: null,
            negotiated_price_max: null,
            service_settings: [],
            summary_count: 0,
            source_count: 0,
            latest_updated: null,
            source_url: null,
          },
        ],
      });
    if (path.includes("/pricing/payers")) return Promise.resolve([]);
    if (path.includes("/pricing/plans")) return Promise.resolve([]);
    return Promise.resolve({
      slug: "mri-brain",
      consumer_name: "MRI brain",
    });
  }),
}));

import ProcedurePrices from "./page";

async function resolveAsyncServerComponents(
  node: ReactNode,
): Promise<ReactNode> {
  if (!isValidElement(node)) return node;

  const element = node as ReactElement<{ children?: ReactNode }>;
  if (
    typeof element.type === "function" &&
    element.type.constructor.name === "AsyncFunction"
  ) {
    const component = element.type as (
      props: typeof element.props,
    ) => Promise<ReactNode>;
    return resolveAsyncServerComponents(await component(element.props));
  }

  const children = element.props.children;
  if (children === undefined) return element;
  const resolvedChildren = await Promise.all(
    React.Children.toArray(children).map(resolveAsyncServerComponents),
  );
  return React.cloneElement(element, undefined, ...resolvedChildren);
}

describe("ProcedurePrices", () => {
  it("shows publishable prices and visible coverage gaps", async () => {
    render(
      await resolveAsyncServerComponents(
        await ProcedurePrices({
          params: Promise.resolve({ slug: "mri-brain" }),
          searchParams: Promise.resolve({ availability: "" }),
        }),
      ),
    );
    expect(
      screen.getByRole("heading", { name: "MRI brain" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Published Hospital")).toBeInTheDocument();
    expect(screen.getByText("Coverage Gap Hospital")).toBeInTheDocument();
  });

  it("supports an unavailable-price filter", async () => {
    render(
      await resolveAsyncServerComponents(
        await ProcedurePrices({
          params: Promise.resolve({ slug: "mri-brain" }),
          searchParams: Promise.resolve({ availability: "unavailable" }),
        }),
      ),
    );
    expect(screen.getByText("Coverage Gap Hospital")).toBeInTheDocument();
    expect(screen.queryByText("Published Hospital")).not.toBeInTheDocument();
  });

  it("renders removable URL-backed active filter chips", async () => {
    render(
      await resolveAsyncServerComponents(
        await ProcedurePrices({
          params: Promise.resolve({ slug: "mri-brain" }),
          searchParams: Promise.resolve({
            location: "Nashua",
            facility_type: "Acute Care Hospital",
            pay: "self",
            availability: "available",
          }),
        }),
      ),
    );

    const locationChip = screen.getByRole("link", {
      name: /Clear filters: Nashua/,
    });
    expect(locationChip).toHaveAttribute(
      "href",
      expect.not.stringContaining("location="),
    );
    expect(locationChip).toHaveAttribute(
      "href",
      expect.stringContaining("facility_type=Acute+Care+Hospital"),
    );
    expect(
      screen.getByRole("link", { name: "Clear all filters" }),
    ).toHaveAttribute("href", "/procedures/mri-brain/prices");
    expect(screen.getByText(/4 active filters/)).toBeInTheDocument();
  });
});
