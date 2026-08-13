"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CareSearch } from "../components/CareSearch";
import { EmptyState, ErrorState, LoadingSkeleton } from "../components/ui";
import type { SearchResult } from "../../lib/api";
import { localePath, messages } from "../../lib/i18n";
import { useLocale } from "../components/useLocale";
import { SearchCategoryResults } from "./SearchCategoryResults";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const SEARCH_TIMEOUT_MS = 10_000;

function SearchContent() {
  const router = useRouter();
  const locale = useLocale();
  const t = messages[locale] ?? messages.en;
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const location = params.get("location") ?? "";
  const payer = params.get("payer") ?? "";
  const [items, setItems] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(q.length >= 2);
  const [error, setError] = useState(false);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);
  const [requestNonce, setRequestNonce] = useState(0);
  useEffect(() => {
    if (q.length < 2) return;
    const controller = new AbortController();
    let timedOut = false;
    const reset = setTimeout(() => {
      setLoading(true);
      setError(false);
    }, 0);
    const query = new URLSearchParams({ q, locale, page_size: "100" });
    if (/^\d{5}$/.test(location)) query.set("postal_code", location);
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, SEARCH_TIMEOUT_MS);
    fetch(`${API_URL}/api/v1/search?${query}`, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((d) => {
        const results = (d.items ?? []) as SearchResult[];
        if (d.clarification_needed) {
          setClarificationQuestion(d.clarification_question ?? t.searchClarificationTitle);
          setItems(results);
          return;
        }
        setClarificationQuestion(null);
        const procedures = results.filter(
          (item) => item.entity_type === "procedure" && item.metadata.slug,
        );
        if (procedures.length === 1 && results.length === 1) {
          const priceParams = new URLSearchParams();
          if (location) priceParams.set("location", location);
          if (payer) priceParams.set("payer", payer);
          const query = priceParams.size ? `?${priceParams}` : "";
          router.replace(
            localePath(
              locale,
              `/procedures/${procedures[0].metadata.slug}/prices${query}`,
            ),
          );
          return;
        }
        setItems(results);
      })
      .catch((e) => {
        if (timedOut || e.name !== "AbortError") setError(true);
      })
      .finally(() => {
        clearTimeout(timeout);
        setLoading(false);
      });
    return () => {
      clearTimeout(reset);
      clearTimeout(timeout);
      controller.abort();
    };
  }, [q, location, payer, requestNonce, router, locale, t.searchClarificationTitle]);
  const category = items.find(
    (item) => item.entity_type === "procedure_category",
  );
  const categoryProcedures = category
    ? items.filter(
        (item) =>
          item.entity_type === "procedure" &&
          item.match_reason === "category_member" &&
          item.metadata.category === category.metadata.slug,
      )
    : [];
  const otherItems = category
    ? items.filter(
        (item) =>
          item.entity_type !== "procedure_category" &&
          item.match_reason !== "category_member",
      )
    : items;
  const priceParams = new URLSearchParams();
  if (location) priceParams.set("location", location);
  if (payer) priceParams.set("payer", payer);
  const procedureQuery = priceParams.size ? `?${priceParams}` : "";
  return (
    <main>
      <div className="page-heading">
        <p className="eyebrow">{t.searchFindCare}</p>
        <h1>
          {q
            ? t.searchResultsFor.replace("{q}", q)
            : t.searchWhatCareTitle}
        </h1>
        <p className="lede">{t.searchIntro}</p>
      </div>
      <CareSearch
        compact
        initialCare={q}
        initialLocation={location}
        initialPayer={payer}
        locale={locale}
      />
      {q && (
        <div className="toolbar">
          <strong>
            {loading
              ? t.searchSearching
              : ((category
                    ? (category.metadata.procedure_count ?? categoryProcedures.length)
                    : items.length) === 1
                  ? t.searchResultCountOne
                  : t.searchResultCountOther
                ).replace(
                  "{count}",
                  String(
                    category
                      ? (category.metadata.procedure_count ?? categoryProcedures.length)
                      : items.length,
                  ),
                )}
          </strong>
          <span className="muted">{t.searchVerifiedOnly}</span>
        </div>
      )}
      {loading ? (
        <LoadingSkeleton messages={t} />
      ) : error ? (
        <ErrorState
          onRetry={() => setRequestNonce((value) => value + 1)}
          messages={t}
        />
      ) : q && items.length === 0 ? (
        <EmptyState title={t.searchNoMatchTitle}>
          {t.searchNoMatchBody}
        </EmptyState>
      ) : clarificationQuestion ? (
        <section className="search-clarification">
          <h2>{clarificationQuestion}</h2>
          <p>{t.searchClarificationBody}</p>
          <SearchCards
            items={items}
            locale={locale}
            location={location}
            payer={payer}
            compareLabel={t.searchCompareCta}
            detailsLabel={t.viewDetails}
          />
        </section>
      ) : category ? (
        <>
          <SearchCategoryResults
            category={category}
            procedures={categoryProcedures}
            locale={locale}
            procedureQuery={procedureQuery}
          />
          {otherItems.length > 0 && (
            <div className="search-other-results">
              <h2>{t.searchOtherMatches}</h2>
              <SearchCards
                items={otherItems}
                locale={locale}
                location={location}
                payer={payer}
                compareLabel={t.searchCompareCta}
                detailsLabel={t.viewDetails}
              />
            </div>
          )}
        </>
      ) : (
        <SearchCards
          items={items}
          locale={locale}
          location={location}
          payer={payer}
          compareLabel={t.searchCompareCta}
          detailsLabel={t.viewDetails}
        />
      )}
    </main>
  );
}

function SearchCards({
  items,
  locale,
  location,
  payer,
  compareLabel,
  detailsLabel,
}: {
  items: SearchResult[];
  locale: ReturnType<typeof useLocale>;
  location: string;
  payer: string;
  compareLabel: string;
  detailsLabel: string;
}) {
  return (
    <div className="cards">
      {items.map((item) => (
            <article
              className="card"
              key={`${item.entity_type}-${item.entity_id}`}
            >
              <span className="badge neutral">
                {item.entity_type.replaceAll("_", " ")}
              </span>
              <h2>{item.title}</h2>
              <p>{item.subtitle}</p>
              {item.location && <p className="location">{item.location}</p>}
              <Link
                className="button"
                href={
                  item.entity_type === "facility"
                    ? localePath(locale, `/hospitals/${item.entity_id}`)
                    : item.entity_type === "procedure"
                      ? localePath(
                          locale,
                          `/procedures/${item.metadata.slug}/prices?location=${encodeURIComponent(location)}${payer ? `&payer=${encodeURIComponent(payer)}` : ""}`,
                        )
                      : localePath(
                          locale,
                          `/procedures?category=${item.metadata.slug}`,
                        )
                }
              >
                {item.entity_type === "procedure"
                  ? compareLabel
                  : detailsLabel}
              </Link>
            </article>
      ))}
    </div>
  );
}
export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <main>
          <LoadingSkeleton />
        </main>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
