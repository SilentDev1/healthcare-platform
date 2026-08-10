import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({
  apiGet: vi.fn().mockResolvedValue({
    nh_facilities: 26,
    facilities_with_publishable_prices: 12,
    publishable_procedures: 48,
  }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
import Home from "./page";

describe("Home", () => {
  it("renders the consumer search and transparent coverage notice", async () => {
    render(await Home());
    expect(
      screen.getByRole("heading", {
        name: "Compare healthcare costs near you",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "What do you need?" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/12 of 26 active hospitals/)).toBeInTheDocument();
    expect(screen.getByText(/not generated estimates/)).toBeInTheDocument();
  });
});
