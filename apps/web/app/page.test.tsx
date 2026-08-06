import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import Home from "./page";
describe("Home", () => {
  it("explains the product", () => {
    render(<Home />);
    expect(screen.getByRole("heading")).toHaveTextContent("Clear information");
  });
});
