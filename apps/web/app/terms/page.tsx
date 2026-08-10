import type { Metadata } from "next";

export const metadata: Metadata = { title: "Beta terms and disclaimers" };

export default function TermsPage() {
  return (
    <main className="state-page">
      <p className="eyebrow">Beta terms and disclaimers</p>
      <h1>Use Carevero as an informational comparison tool</h1>
      <p>
        Carevero organizes public hospital transparency files and CMS quality
        data. Information may contain source errors, omissions, or delays and
        may change. A displayed amount is not a quote or guarantee of your final
        bill.
      </p>
      <h2>Insurance and quality</h2>
      <p>
        A published negotiated rate does not establish that a provider is in
        your network or that your plan will cover a service. Confirm benefits,
        authorization, provider participation, and expected charges directly
        with the hospital and insurer. Quality information is context, not a
        medical recommendation or a declaration of the best provider.
      </p>
      <h2>Medical decisions</h2>
      <p>
        Carevero does not provide medical advice. Discuss care decisions with a
        qualified healthcare professional.
      </p>
      <p className="muted">
        These beta terms require legal review before a broad public launch.
      </p>
    </main>
  );
}
