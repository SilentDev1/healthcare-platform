import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import AdminHome from "./page";
describe("AdminHome", () => {
  it("labels operations", () => {
    render(<AdminHome />);
    expect(screen.getByRole("heading")).toHaveTextContent("operations");
  });
});
