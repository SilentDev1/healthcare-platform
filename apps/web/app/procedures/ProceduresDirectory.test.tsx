import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { locales, messages, type Locale } from "../../lib/i18n";
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

  /* ---- COUNT SEMANTICS ---- */

  it('displays "1 procedure" (singular) when one result matches', () => {
    renderDirectory(new URLSearchParams("q=colonoscopy"));
    expect(screen.getByText(/1 procedure\b/)).toBeInTheDocument();
  });

  it('displays plural "{count} procedures" when multiple results match', () => {
    renderDirectory();
    // 4 non-ED procedures displayed as cards
    expect(screen.getByText(/4 procedures/)).toBeInTheDocument();
  });

  it("category sidebar count is a procedure count, not a facility count", () => {
    renderDirectory();
    // "Imaging" category has exactly 2 procedures (MRI + mammogram)
    // This is a procedure count — not a facility or location count.
    const sidebarButtons = screen.getAllByRole("button").filter((btn) =>
      btn.textContent?.includes("Imaging"),
    );
    expect(sidebarButtons.length).toBeGreaterThan(0);
    const countText = sidebarButtons[0].textContent;
    // Should show "2" (the number of procedures in imaging)
    expect(countText).toContain("2");
    // Should NOT show any large number that would suggest facility counts
    expect(countText).not.toMatch(/\d{2,}/);
  });

  /* ---- SLUG LEAKING ---- */

  it("never exposes internal taxonomy slugs in rendered output", () => {
    // Add a procedure with a slug-like category that could leak
    const procsWithUnknownCat: Procedure[] = [
      makeProcedure({
        id: "pX",
        slug: "some-procedure",
        consumer_name: "Some procedure",
        category: {
          slug: "outpatient_surgery",
          name: "Outpatient Surgery",
          description: "",
        },
      }),
    ];
    state.searchParams = new URLSearchParams();
    render(
      <ProceduresDirectory
        procedures={procsWithUnknownCat}
        categories={CATEGORIES}
        locale="en"
        messages={t}
      />,
    );
    // Should show the consumer-friendly name "Outpatient surgery", not raw slug
    expect(screen.getAllByText("Outpatient surgery").length).toBeGreaterThan(0);
    // Raw slug "outpatient_surgery" should never appear in rendered text
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("outpatient_surgery");
  });

  it("humanizes unknown category slugs instead of leaking raw text", () => {
    const procsWithNewCat: Procedure[] = [
      makeProcedure({
        id: "pY",
        slug: "some-new-procedure",
        consumer_name: "New procedure",
        category: {
          slug: "sports_medicine",
          name: "Sports Medicine",
          description: "",
        },
      }),
    ];
    state.searchParams = new URLSearchParams();
    render(
      <ProceduresDirectory
        procedures={procsWithNewCat}
        categories={CATEGORIES}
        locale="en"
        messages={t}
      />,
    );
    // Should humanize to "Sports Medicine" not expose "sports_medicine"
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("sports_medicine");
    expect(body).toContain("Sports Medicine");
  });

  /* ---- URL STATE ---- */

  it("URL state survives by reading from searchParams", () => {
    // Simulate a page load with query params already set
    renderDirectory(new URLSearchParams("category=laboratory&q=CBC&sort=za"));
    // CBC should be visible (search + category match)
    expect(
      screen.getByText("Complete blood count (CBC)"),
    ).toBeInTheDocument();
    // MRI should not be visible
    expect(
      screen.queryByText("MRI knee without contrast"),
    ).not.toBeInTheDocument();
  });

  /* ---- CONSUMER CATEGORY NAMES ---- */

  it("shows translated consumer category names, not raw API names", () => {
    renderDirectory();
    // "laboratory" category should render as "Lab tests" (from procCat_laboratory)
    expect(screen.getAllByText("Lab tests").length).toBeGreaterThan(0);
    // "emergency" category should render as "Emergency care" (from procCat_emergency)
    expect(screen.getAllByText("Emergency care").length).toBeGreaterThan(0);
    // Raw API names should not appear
    const body = document.body.textContent ?? "";
    // "Laboratory" (raw API name) would only appear if slug leaks — but "Lab tests" is used
    // Note: "Imaging" and "Gastroenterology" happen to match their API names, so we check laboratory/emergency
    expect(body).not.toContain("laboratory");
  });
});

/* ------------------------------------------------------------------ */
/* i18n placeholder parity across all 5 locales                        */
/* ------------------------------------------------------------------ */

describe("i18n placeholder parity", () => {
  const PLACEHOLDER_RE = /\{(\w+)\}/g;

  function extractPlaceholders(str: string): string[] {
    return [...str.matchAll(PLACEHOLDER_RE)].map((m) => m[1]).sort();
  }

  const keysWithPlaceholders = Object.entries(messages.en).filter(
    ([, value]) => typeof value === "string" && PLACEHOLDER_RE.test(value),
  );

  for (const [key] of keysWithPlaceholders) {
    const enValue = messages.en[key as keyof typeof messages.en] as string;
    const enPlaceholders = extractPlaceholders(enValue);

    for (const locale of locales) {
      if (locale === "en") continue;
      it(`${key}: ${locale} has same placeholders as en`, () => {
        const localeMessages = messages[locale];
        const localeValue = localeMessages[key as keyof typeof localeMessages];
        expect(typeof localeValue).toBe("string");
        const localePlaceholders = extractPlaceholders(localeValue as string);
        expect(localePlaceholders).toEqual(enPlaceholders);
      });
    }
  }
});

/* ------------------------------------------------------------------ */
/* No new hardcoded consumer English in ProceduresDirectory            */
/* ------------------------------------------------------------------ */

describe("No hardcoded English in ProceduresDirectory", () => {
  beforeEach(() => {
    state.searchParams = new URLSearchParams();
    replace.mockClear();
  });

  it("all user-facing text comes from i18n, not hardcoded strings", () => {
    // Render with a non-English locale's messages to verify
    // If any English text leaks, it means something is hardcoded
    const esMessages = messages.es;
    render(
      <ProceduresDirectory
        procedures={PROCEDURES}
        categories={CATEGORIES}
        locale="es"
        messages={esMessages}
      />,
    );
    const body = document.body.textContent ?? "";
    // The Spanish version should NOT contain these English-only strings
    // (procedure names and aliases are data, not UI text, so they'll still be English)
    expect(body).not.toContain("All procedures");
    expect(body).not.toContain("Common searches");
    expect(body).not.toContain("View prices");
    expect(body).not.toContain("Don't see a procedure?");
    expect(body).not.toContain("Prices not available everywhere");
    // Spanish equivalents should be present
    expect(body).toContain(esMessages.procDirAllProcedures);
    expect(body).toContain(esMessages.procDirViewPrices);
    expect(body).toContain(esMessages.procDirDontSeeTitle);
  });
});
