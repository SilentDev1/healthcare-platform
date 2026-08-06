import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({
  apiGet: vi.fn().mockResolvedValue({
    items: [
      {
        id: "1",
        display_name: "Concord Hospital",
        facility_type: "Acute Care",
        locations: [{ city: "Concord" }],
      },
    ],
    total: 1,
  }),
}));
import Home from "./page";

describe("Home", () => {
  it("renders the NH directory and pricing notice", async () => {
    render(await Home());
    expect(
      screen.getByRole("heading", { name: "Find a New Hampshire hospital." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Concord Hospital" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Pricing comparison is coming later/),
    ).toBeInTheDocument();
  });
});
