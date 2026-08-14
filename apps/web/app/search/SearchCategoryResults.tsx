import type { SearchResult } from "../../lib/api";
import { messages, type Locale } from "../../lib/i18n";
import { ProcedureCard } from "../components/ProcedureCard";

export function SearchCategoryResults({
  category,
  procedures,
  locale,
  procedureQuery,
}: {
  category: SearchResult;
  procedures: SearchResult[];
  locale: Locale;
  procedureQuery: string;
}) {
  const t = messages[locale] ?? messages.en;
  const procedureCount = category.metadata.procedure_count ?? procedures.length;
  return (
    <section className="search-category-results">
      <div className="search-category-summary">
        <p className="eyebrow">{category.title}</p>
        <h2>
          {(procedureCount === 1
            ? t.searchCategoryCountOne
            : t.searchCategoryCountOther
          ).replace("{count}", String(procedureCount))}
        </h2>
        <p>{t.searchCategoryChooseProcedure}</p>
      </div>
      <div className="procdir-cards">
        {procedures.map((item) => (
          <ProcedureCard
            key={item.entity_id}
            id={item.entity_id}
            slug={item.metadata.slug ?? ""}
            name={item.title}
            locale={locale}
            viewPricesLabel={t.procDirViewPrices}
            query={procedureQuery}
          />
        ))}
      </div>
    </section>
  );
}
