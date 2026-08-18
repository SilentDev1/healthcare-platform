import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AskCarevero } from "./AskCarevero";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock("../components/FacilityImage", () => ({ FacilityImage: () => <span data-testid="facility-image" /> }));

const procedure = (title: string, slug: string) => ({ entity_type: "procedure", entity_id: slug, title, subtitle: "", location: null, metadata: { slug } });
function response(body: unknown) { return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response); }
function submit(text: string) { fireEvent.change(screen.getByLabelText(/procedure, provider/i), { target: { value: text } }); fireEvent.click(screen.getByRole("button", { name: "Send" })); }

describe("AskCarevero", () => {
  beforeEach(() => { vi.restoreAllMocks(); Element.prototype.scrollIntoView = vi.fn(); });
  afterEach(() => cleanup());

  it("renders a readable user bubble and clarifies a self-pay lab category with real choices", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockImplementationOnce(() => response({ domain: "carevero", intent_type: "category", candidate_slugs: ["laboratory"] }))
      .mockImplementationOnce(() => response({ intent_type: "category", canonical_category_slug: "laboratory", payment_context: "self_pay", items: [procedure("Complete blood count (CBC)", "complete-blood-count"), procedure("Comprehensive metabolic panel", "comprehensive-metabolic-panel")] })));
    render(<AskCarevero locale="en" />); submit("I need a blood test with no insurance");
    const bubble = await screen.findByLabelText("You said");
    expect(bubble).toHaveClass("ask-user");
    expect(await screen.findByText("Self-pay / no insurance")).toBeInTheDocument();
    expect(screen.getByText("Laboratory")).toBeInTheDocument();
    expect(screen.getByText(/can mean several different tests/i)).toBeInTheDocument();
    expect(screen.queryByText(/Service:/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Compare self-pay prices: Complete blood count/ })).toHaveAttribute("href", expect.stringContaining("pay=self"));
  });

  it("renders grounded exact-procedure price cards", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockImplementationOnce(() => response({ domain: "carevero", intent_type: "procedure", candidate_slugs: ["complete-blood-count"] }))
      .mockImplementationOnce(() => response({ intent_type: "procedure", payment_context: "self_pay", items: [procedure("Complete blood count", "complete-blood-count")] }))
      .mockImplementationOnce(() => response({ items: [{ facility_id: "f1", facility_name: "Nashua Lab", city: "Nashua", cash_price_min: "42", negotiated_price_min: null }] })));
    render(<AskCarevero locale="en" />); submit("How much is a CBC without insurance?");
    expect(await screen.findByText("$42")).toBeInTheDocument();
    expect(screen.getByText("Published cash/self-pay price")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Compare all self-pay prices/ })).toHaveAttribute("href", expect.stringContaining("pay=self"));
  });

  it("renders medical refusals and safe navigation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => response({ domain: "medical_advice", intent_type: "unknown", candidate_slugs: [], refusal_message: "Carevero can help with prices and providers, but it can't recommend which test you medically need." })));
    render(<AskCarevero locale="en" />); submit("My knee hurts, what scan do I need?");
    expect(await screen.findByText(/can't recommend which test/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse procedures" })).toBeInTheDocument();
  });

  it("renders out-of-scope boundaries and price explanations without result cards", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => response({ domain: "carevero", intent_type: "unknown", candidate_slugs: [] })));
    const { unmount } = render(<AskCarevero locale="en" />); submit("What does discounted cash price mean?");
    expect(await screen.findByText(/provider’s published price/i)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Procedure choices" })).not.toBeInTheDocument();
    unmount();
    vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => response({ domain: "out_of_scope", intent_type: "unknown", candidate_slugs: [], refusal_message: null })));
    render(<AskCarevero locale="en" />); submit("Write me a poem");
    await waitFor(() => expect(screen.getByText(/healthcare services, providers/i)).toBeInTheDocument());
  });
});
