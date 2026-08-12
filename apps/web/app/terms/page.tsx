import type { Metadata } from "next";
import { requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = { title: "Beta terms and disclaimers" };

export default async function TermsPage() {
  const t = await requestMessages();
  return (
    <main className="state-page">
      <p className="eyebrow">{t.termsEyebrow}</p>
      <h1>{t.termsTitle}</h1>
      <p>{t.termsIntro}</p>
      <h2>{t.termsInsuranceHeading}</h2>
      <p>{t.termsInsuranceBody}</p>
      <h2>{t.termsMedicalHeading}</h2>
      <p>{t.termsMedicalBody}</p>
      <p className="muted">{t.termsReviewNote}</p>
    </main>
  );
}
