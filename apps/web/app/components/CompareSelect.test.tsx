import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { CompareSelect, CompareTray } from "./CompareSelect";

beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

describe("anonymous comparison state", () => {
  it("is scoped to a procedure and preserves payer URL state", () => {
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
        <CompareTray procedureSlug="mri-knee" payer="aetna" />
      </>,
    );
    fireEvent.click(screen.getByLabelText(/Add Main campus/));
    fireEvent.click(screen.getByLabelText(/Add Downtown campus/));
    const link = screen.getByRole("link", { name: "Compare 2" });
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("payer=aetna"),
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
});
