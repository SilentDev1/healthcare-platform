import Link from "next/link";
import { PopularSearches } from "../components/PopularSearches";
import { consumerCategoryName, consumerCategoryRegistry } from "../../lib/procedureCategories";
import { localePath, type Locale, type Messages } from "../../lib/i18n";

export function SearchDiscovery({ locale, messages }: { locale: Locale; messages: Messages }) {
  return <div className="search-discovery">
    <PopularSearches locale={locale} heading={messages.popular} viewAllLabel={messages.viewAllProcedures} />
    <section className="discovery-section"><div className="section-heading"><p className="eyebrow">{messages.procedures}</p><h2>{messages.procedures}</h2></div><div className="discovery-category-grid">{Array.from(consumerCategoryRegistry.keys()).slice(0, 9).map((slug) => <Link key={slug} href={`${localePath(locale,"/search")}?q=${encodeURIComponent(consumerCategoryName(messages, slug))}`}><span>{consumerCategoryName(messages, slug)}</span><span aria-hidden="true">→</span></Link>)}</div></section>
    <section className="selfpay-discovery"><div><p className="eyebrow">{messages.selfPay}</p><h2>{messages.selfPayTitle}</h2><p>{messages.selfPayPrompt}</p></div><Link className="button" href={`${localePath(locale,"/search")}?q=blood%20tests&pay=self`}>{messages.selfPayShowCash} →</Link></section>
    <section className="discovery-steps" aria-label={messages.howItWorks}><article><strong>1</strong><h3>{messages.homeStepSearchTitle}</h3><p>{messages.homeStepSearchBody}</p></article><article><strong>2</strong><h3>{messages.homeStepCompareTitle}</h3><p>{messages.homeStepCompareBody}</p></article><article><strong>3</strong><h3>{messages.homeStepVerifyTitle}</h3><p>{messages.homeStepVerifyBody}</p></article></section>
  </div>;
}
