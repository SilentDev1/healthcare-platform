import type { Metadata } from "next";
import { requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = { title: "Beta privacy notice" };

export default async function PrivacyPage() {
  const t = await requestMessages();
  return (
    <main className="state-page">
      <p className="eyebrow">{t.privEyebrow}</p>
      <h1>{t.privTitle}</h1>
      <p>{t.privIntro}</p>
      <h2>{t.privWhatProcessedHeading}</h2>
      <p>{t.privWhatProcessedBody}</p>
      <h2>{t.privBoundariesHeading}</h2>
      <p>{t.privBoundariesBody}</p>
      <p className="muted">{t.privReviewNote}</p>
    </main>
  );
}
