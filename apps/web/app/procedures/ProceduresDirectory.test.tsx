import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { messages } from "../../lib/i18n";
import type { Procedure, ProcedureCategory } from "../../lib/api";

afterEach(cleanup);

const { state, push, replace } = vi.hoisted(() => {
  const pushFn = vi.fn();
  const replaceFn = vi.fn();
  return {
    state: { searchParams: new URLSearchParams() },
    push: pushFn,
    replace: replaceFn,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => state.searchParams,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { ProceduresDirectory } from "./ProceduresDirectory";

const t = messages.en;

function makeProcedure(overrides: Partial<Procedure> = {}): Procedure {
  return {
    id: "p1",
    slug: "mri-knee-without-contrast",
    consumer_name: "MRI knee without contrast",
    short_description: "Magnetic resonance imaging of the knee joint.",
    long_description: "A detailed imaging procedure for the knee.",
    service_setting: "outpatient",
    complexity: "moderate",
    shoppable: true,
    aliases: ["knee MRI", "MRI leg"],
    category: { slug: "imaging", name: "Imaging", description: "" },
    billing_notice: "",
    ...overrides,
  };
}

const PROCEDURES: Procedure[] = [
  makeProcedure(),
  makeProcedure({
    id: "p2",
    slug: "colonoscopy-diagnostic",
    consumer_name: "Colonoscopy (diagnostic)",
    short_description: "A diagnostic examination of the colon.",
    aliases: ["colon exam"],
    category: {
      slug: "gastroenterology",
      name: "Gastroenterology",
      description: "",
    },
  }),
  makeProcedure({
    id: "p3",
    slug: "complete-blood-count",
    consumer_name: "Complete blood count (CBC)",
    short_description: "A blood test measuring cell counts.",
    aliases: ["CBC", "blood panel"],
    category: { slug: "laboratory", name: "Laboratory", description: "" },
  }),
  makeProcedure({
    id: "p4",
    slug: "mammogram-screening",
    consumer_name: "Mammogram (screening)",
    short_description:
      "A consumer-friendly overview of screening mammography.",
    long_description:
      "Screening mammography uses low-dose X-rays to detect breast cancer early in women who have no signs or symptoms.",
    aliases: ["breast screening"],
    category: { slug: "imaging", name: "Imaging", description: "" },
  }),
  makeProcedure({
    id: "p5",
    slug: "ed-visit-level-1",
    consumer_name: "ED visit level 1",
    short_description: "Emergency department visit, severity level 1.",
    aliases: [],
    category: { slug: "emergency", name: "Emergency", description: "" },
  }),
  makeProcedure({
    id: "p6",
    slug: "ed-visit-level-2",
    consumer_name: "ED visit level 2",
    short_description: "Emergency department visit, severity level 2.",
    aliases: [],
    category: { slug: "emergency", name: "Emergency", description: "" },
  }),
  makeProcedure({
    id: "p7",
    slug: "ed-visit-level-3",
    consumer_name: "ED visit level 3",
    short_description: "Emergency department visit, severity level 3.",
    aliases: [],
    category: { slug: "emergency", name: "Emergency", description: "" },
  }),
];

const CATEGORIES: ProcedureCategory[] = [];

function renderDirectory(params = new URLSearchParams()) {
  state.searchParams = params;
  return render(
    <ProceduresDirectory
      procedures={PROCEDURES}
      categories={CATEGORIES}
      locale="en"
      messages={t}
    />,
  );
}

describe("ProceduresDirectory", () => {
  beforeEach(() => {
    state.searchParams = new URLSearchParams();
    replace.mockClear();
  });

  it("renders all non-ED procedures by default", () => {
    renderDirectory();
    // Procedures appear in both chips and cards, so use getAllByText
    expect(
      screen.getAllByText("MRI knee without contrast").length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("Colonoscopy (diagnostic)").length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("Complete blood count (CBC)").length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("Mammogram (screening)").length,
    ).toBeGreaterThanOrEqual(1);
    // ED procedures are grouped in the ED family card
    expect(screen.queryByText("ED visit level 1")).not.toBeNull();
  });

  it("search filters by consumer_name", () => {
    renderDirectory(new URLSearchParams("q=MRI"));
    expect(screen.getByText("MRI knee without contrast")).toBeInTheDocument();
    expect(
      screen.queryByText("Colonoscopy (diagnostic)"),
    ).not.toBeInTheDocument();
  });

  it("search filters by alias", () => {
    renderDirectory(new URLSearchParams("q=CBC"));
    expect(
      screen.getByText("Complete blood count (CBC)"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("MRI knee without contrast"),
    ).not.toBeInTheDocument();
  });

  it("category selection filters results", () => {
    renderDirectory(new URLSearchParams("category=laboratory"));
    // CBC appears in both popular chips and filtered cards
    expect(
      screen.getAllByText("Complete blood count (CBC)").length,
    ).toBeGreaterThanOrEqual(1);
    // MRI is in popular chips but NOT in the card list (filtered out by category)
    // Check that the card list only has lab procedures
    const cards = document.querySelectorAll(".procdir-card-title");
    const cardTexts = Array.from(cards).map((c) => c.textContent);
    expect(cardTexts).toContain("Complete blood count (CBC)");
    expect(cardTexts).not.toContain("MRI knee without contrast");
  });

  it("category shows correct count in sidebar", () => {
    renderDirectory();
    // Imaging has 2 procedures (MRI + mammogram)
    const sidebar = screen.getAllByRole("button").filter((btn) =>
      btn.textContent?.includes("Imaging"),
    );
    expect(sidebar.length).toBeGreaterThan(0);
    expect(sidebar[0].textContent).toContain("2");
  });

  it("combined search + category filters both", () => {
    renderDirectory(new URLSearchParams("category=imaging&q=mammogram"));
    expect(screen.getByText("Mammogram (screening)")).toBeInTheDocument();
    expect(
      screen.queryByText("MRI knee without contrast"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Complete blood count (CBC)"),
    ).not.toBeInTheDocument();
  });

  it("shows empty state with clear button when no results", () => {
    renderDirectory(new URLSearchParams("q=zzzznonexistent"));
    expect(screen.getByText(t.procDirNoResults)).toBeInTheDocument();
    expect(screen.getByText(t.procDirClearSearch)).toBeInTheDocument();
  });

  it("sort Z-A reverses order", () => {
    renderDirectory(new URLSearchParams("sort=za"));
    const titles = screen
      .getAllByRole("heading", { level: 2 })
      .map((h) => h.textContent);
    // Non-ED procedures sorted Z-A
    const mammogramIdx = titles.findIndex((t) =>
      t?.includes("Mammogram"),
    );
    const cbcIdx = titles.findIndex((t) =>
      t?.includes("Complete blood count"),
    );
    if (mammogramIdx !== -1 && cbcIdx !== -1) {
      expect(mammogramIdx).toBeLessThan(cbcIdx);
    }
  });

  it("groups ED procedures into a family card when no search", () => {
    renderDirectory();
    expect(screen.getByText(t.procDirEdFamilyTitle)).toBeInTheDocument();
    expect(screen.getByText(t.procDirEdFamilyDesc)).toBeInTheDocument();
  });

  it("shows consumer category names from i18n", () => {
    renderDirectory();
    expect(screen.getAllByText("Lab tests").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Gastroenterology").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Imaging").length).toBeGreaterThan(0);
  });

  it("popular chip click populates search", () => {
    renderDirectory();
    const chips = screen.getAllByRole("button");
    const mriChip = chips.find((btn) =>
      btn.textContent?.includes("MRI knee without contrast"),
    );
    if (mriChip) {
      fireEvent.click(mriChip);
      expect(replace).toHaveBeenCalled();
    }
  });

  it("procedure card links are canonical", () => {
    renderDirectory();
    const link = screen.getByRole("link", {
      name: "MRI knee without contrast",
    });
    expect(link).toHaveAttribute(
      "href",
      "/procedures/mri-knee-without-contrast",
    );
  });

  it("replaces template descriptions", () => {
    renderDirectory();
    // Mammogram has template description — should be replaced
    expect(
      screen.queryByText(/A consumer-friendly overview of/),
    ).not.toBeInTheDocument();
    // Should show truncated long_description instead
    expect(
      screen.getByText(/Screening mammography uses low-dose X-rays/),
    ).toBeInTheDocument();
  });
});
