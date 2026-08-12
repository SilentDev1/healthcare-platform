import { requestMessages } from "../../lib/i18n-server";

export default async function Loading() {
  const t = await requestMessages();
  return (
    <main>
      <h1>{t.loadingMap}</h1>
    </main>
  );
}
