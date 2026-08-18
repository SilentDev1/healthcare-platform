import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExperienceTrigger, GlobalExperience } from "./GlobalExperience";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("../ask/AskCarevero", () => ({ AskCarevero: () => <div>Shared Ask conversation</div> }));
afterEach(() => cleanup());

describe("global consumer experiences", () => {
  it("opens and closes quick search, restores focus, and keeps full search available", () => {
    render(<><ExperienceTrigger kind="search">Search prices</ExperienceTrigger><GlobalExperience locale="en" /></>);
    const trigger = screen.getByRole("button", { name: "Search prices" }); trigger.focus(); fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "Find a healthcare price" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open full search/ })).toHaveAttribute("href", "/search");
    fireEvent.keyDown(document, { key: "Escape" }); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("submits query, location, and self-pay as canonical URL state", () => {
    render(<><ExperienceTrigger kind="search">Search prices</ExperienceTrigger><GlobalExperience locale="en" /></>);
    fireEvent.click(screen.getByRole("button", { name: "Search prices" }));
    fireEvent.change(screen.getByLabelText("What are you looking for?"), { target: { value: "CBC" } });
    fireEvent.change(screen.getByLabelText("Where?"), { target: { value: "03060" } });
    fireEvent.click(screen.getByLabelText("Self-pay / no insurance")); fireEvent.click(screen.getByRole("button", { name: /Search prices →/ }));
    expect(push).toHaveBeenCalledWith("/search?q=CBC&location=03060&pay=self");
  });

  it("opens the Ask drawer and provides the full-page escape hatch", async () => {
    render(<><ExperienceTrigger kind="ask">Ask Carevero</ExperienceTrigger><GlobalExperience locale="en" /></>);
    fireEvent.click(screen.getByRole("button", { name: "Ask Carevero" }));
    expect(await screen.findByRole("dialog", { name: "Ask Carevero" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open full Ask Carevero/ })).toHaveAttribute("href", "/ask");
  });
});
