import type { Metadata } from "next";

export const metadata: Metadata = { title: "Beta privacy notice" };

export default function PrivacyPage() {
  return (
    <main className="state-page">
      <p className="eyebrow">Beta privacy notice</p>
      <h1>Privacy at Carevero</h1>
      <p>
        Carevero’s core price-comparison experience does not require an account.
        We do not provide medical-record features and do not intentionally
        collect diagnoses, medical records, insurance member IDs, or other
        private medical information.
      </p>
      <h2>What is processed</h2>
      <p>
        Search terms and location choices are processed to return results.
        Hosting systems may keep short-lived standard technical logs such as
        request time, route, status, approximate network address, browser
        information, and a correlation ID for reliability and security. Carevero
        does not use those logs to build identifiable healthcare-interest
        profiles.
      </p>
      <h2>Current product boundaries</h2>
      <p>
        Carevero has no advertising platform and does not sell patient medical
        records. Beta feedback is handled through the displayed contact
        destination; please do not include private medical information or
        attachments.
      </p>
      <p className="muted">
        This beta notice describes the current product and requires legal review
        before a broad public launch.
      </p>
    </main>
  );
}
