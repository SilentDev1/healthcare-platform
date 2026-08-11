import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  CompareSelect,
  CompareTray,
  InlineComparePanel,
} from "./CompareSelect";
import type { ProcedureComparisonItem } from "../../lib/api";

beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

describe("anonymous comparison state", () => {
  it("is scoped to a procedure and preserves payer and plan URL state", () => {
    render(
      <>
        <CompareSelect
          facilityId="f1"
          locationId="l1"
          name="Main campus"
          procedureSlug="mri-knee"
        />
        <CompareSelect
          facilityId="f2"
          locationId="l2"
          name="Downtown campus"
          procedureSlug="mri-knee"
        />
        <CompareTray procedureSlug="mri-knee" payer="aetna" plan="plan-1" />
      </>,
    );
    fireEvent.click(screen.getByLabelText(/Add Main campus/));
    fireEvent.click(screen.getByLabelText(/Add Downtown campus/));
    const link = screen.getByRole("link", { name: /Compare now/ });
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("payer=aetna"),
    );
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("plan=plan-1"),
    );
    expect(sessionStorage.getItem("careveroCompareV1:mri-knee")).toContain(
      "f1~l1",
    );
    expect(sessionStorage.getItem("careveroCompareV1:mri-brain")).toBeNull();
  });

  it("explains and prevents a fourth selection", () => {
    sessionStorage.setItem(
      "careveroCompareV1:mri-knee",
      JSON.stringify([
        { key: "f1~l1", facilityId: "f1", locationId: "l1", name: "One" },
        { key: "f2~l2", facilityId: "f2", locationId: "l2", name: "Two" },
        { key: "f3~l3", facilityId: "f3", locationId: "l3", name: "Three" },
      ]),
    );
    render(
      <CompareSelect
        facilityId="f4"
        locationId="l4"
        name="Fourth"
        procedureSlug="mri-knee"
      />,
    );
    expect(
      screen.getByRole("button", { name: /Add Fourth to comparison/ }),
    ).toBeDisabled();
    expect(
      screen.getByText(/3 selected — remove one to add/),
    ).toBeInTheDocument();
  });

  it("shows three selected hospitals with their real price values", () => {
    const item = (
      facilityId: string,
      locationId: string,
      name: string,
      cash: string,
    ): ProcedureComparisonItem => ({
      facility_id: facilityId,
      facility_name: name,
      facility_location_id: locationId,
      location_name: null,
      location_type: "hospital_campus",
      address_line_1: "1 Main St",
      city: "Concord",
      state: "NH",
      postal_code: "03301",
      facility_type: "Hospital",
      cms_overall_rating: null,
      price_available: true,
      cash_price_min: cash,
      cash_price_max: cash,
      negotiated_price_min: "500",
      negotiated_price_max: "900",
      service_settings: ["outpatient"],
      summary_count: 2,
      source_count: 1,
      latest_updated: "2026-08-10T00:00:00Z",
      source_url: "https://hospital.example/source.csv",
    });
    const items = [
      item("f1", "l1", "One Hospital", "700"),
      item("f2", "l2", "Two Hospital", "800"),
      item("f3", "l3", "Three Hospital", "900"),
    ];
    sessionStorage.setItem(
      "careveroCompareV1:mri-knee",
      JSON.stringify(
        items.map((value) => ({
          key: `${value.facility_id}~${value.facility_location_id}`,
          facilityId: value.facility_id,
          locationId: value.facility_location_id,
          name: value.facility_name,
        })),
      ),
    );
    render(
      <InlineComparePanel
        procedureSlug="mri-knee"
        procedureName="MRI knee"
        items={items}
      />,
    );
    expect(screen.getByText("3 of 3 selected")).toBeInTheDocument();
    expect(screen.getByText("$700")).toBeInTheDocument();
    expect(screen.getByText("$800")).toBeInTheDocument();
    expect(screen.getByText("$900")).toBeInTheDocument();
    expect(screen.queryByText("$500 – $900")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /View full comparison/ }),
    ).toHaveAttribute("href", expect.stringContaining("f3%7El3"));
  });
});
