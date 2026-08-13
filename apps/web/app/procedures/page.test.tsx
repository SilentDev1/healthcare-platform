import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../lib/api", () => ({
  apiGet: vi.fn().mockImplementation((path: string) => {
    if (path.includes("procedure-categories"))
      return Promise.resolve({ items: [] });
    return Promise.resolve({
      items: [
        {
          id: "p1",
          slug: "mri-knee",
          consumer_name: "MRI knee",
          short_description: "Imaging of the knee.",
          long_description: "Detailed knee MRI.",
          service_setting: "outpatient",
          complexity: "moderate",
          shoppable: true,
          aliases: [],
          category: { slug: "imaging", name: "Imaging", description: "" },
          billing_notice: "",
        },
      ],
    });
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import Procedures from "./page";

describe("Procedures page (server component)", () => {
  it("renders without error and passes data to client component", async () => {
    render(
      await Procedures({ searchParams: Promise.resolve({}) }),
    );
    expect(screen.getByText("MRI knee")).toBeInTheDocument();
  });

  it("renders error state when API fails", async () => {
    const { apiGet } = await import("../../lib/api");
    (apiGet as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("API down"),
    );
    render(
      await Procedures({ searchParams: Promise.resolve({}) }),
    );
    expect(
      screen.getByText("Procedure data is unavailable."),
    ).toBeInTheDocument();
  });
});
