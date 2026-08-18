import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GlobalExperience } from "./GlobalExperience";
import { NavigationHeader } from "./NavigationHeader";

let pathname = "/";
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(() => {
  cleanup();
  pathname = "/";
});

describe("consumer navigation header", () => {
  it("opens Find care with working search, procedure, map, and self-pay actions", () => {
    render(
      <>
        <NavigationHeader locale="en" languageLabel="Language" />
        <GlobalExperience locale="en" />
      </>,
    );
    const trigger = screen.getByRole("button", { name: /Find care/ });
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("menuitem", { name: /Browse procedures/ }),
    ).toHaveAttribute("href", "/procedures");
    expect(
      screen.getByRole("menuitem", { name: /Explore map/ }),
    ).toHaveAttribute("href", "/map");
    expect(
      screen.getByRole("menuitem", { name: /Self-pay options/ }),
    ).toHaveAttribute("href", "/search?pay=self");
    fireEvent.click(screen.getByRole("button", { name: /Search prices/ }));
    expect(
      screen.getByRole("dialog", { name: "Find a healthcare price" }),
    ).toBeInTheDocument();
  });

  it("supports Escape, outside click, Ask, language, and active state", () => {
    pathname = "/providers";
    render(
      <>
        <NavigationHeader locale="en" languageLabel="Language" />
        <GlobalExperience locale="en" />
      </>,
    );
    expect(screen.getByRole("link", { name: "Providers" })).toHaveClass(
      "is-active",
    );
    fireEvent.click(screen.getByRole("button", { name: /About/ }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("button", { name: /About/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    fireEvent.click(screen.getByRole("button", { name: /Find care/ }));
    fireEvent.mouseDown(document.body);
    expect(screen.getByRole("button", { name: /Find care/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.getByRole("combobox", { name: "Language" })).toHaveValue(
      "en",
    );
    fireEvent.click(screen.getByRole("button", { name: "✨ Ask Carevero" }));
    expect(
      screen.getByRole("dialog", { name: "Ask Carevero" }),
    ).toBeInTheDocument();
  });

  it("opens and closes the mobile menu while keeping mobile Ask one tap away", () => {
    render(
      <>
        <NavigationHeader locale="en" languageLabel="Language" />
        <GlobalExperience locale="en" />
      </>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    expect(screen.getByRole("dialog", { name: "Menu" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Browse procedures" }),
    ).toHaveAttribute("href", "/procedures");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(
      screen.queryByRole("dialog", { name: "Menu" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "✨ Ask" }));
    expect(
      screen.getByRole("dialog", { name: "Ask Carevero" }),
    ).toBeInTheDocument();
  });
});
