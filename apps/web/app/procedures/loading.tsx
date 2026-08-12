import { requestMessages } from "../../lib/i18n-server";

export default async function Loading() {
  const t = await requestMessages();
  return (
    <main>
      <p>{t.loadingProcedures}</p>
    </main>
  );
}
