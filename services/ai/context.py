from __future__ import annotations

from services.ai.schemas import AIFacilityFact, CareSearchIntent, CareveroAIContext, SourceContext
from services.api.app.schemas import ProcedureComparisonResponse


def build_context(
    intent: CareSearchIntent, comparison: ProcedureComparisonResponse
) -> CareveroAIContext:
    facilities: list[AIFacilityFact] = []
    for item in comparison.items[:25]:
        sources: list[SourceContext] = []
        if item.source_url:
            sources.append(
                SourceContext(
                    fact_type="hospital_mrf",
                    label="Hospital's published price file",
                    source_url=item.source_url,
                    last_checked=item.carevero_refresh_date or item.imported_at,
                )
            )
        if item.cms_overall_rating is not None:
            sources.append(SourceContext(fact_type="cms_care_compare", label="CMS Care Compare"))
        if item.published_price_difference is not None:
            sources.append(
                SourceContext(
                    fact_type="carevero_calculation",
                    label="Carevero deterministic comparable-price calculation",
                )
            )
        facilities.append(
            AIFacilityFact(
                id=item.facility_id,
                name=item.facility_name,
                city=item.city,
                state=item.state,
                distance_miles=item.distance_miles,
                cms_rating=item.cms_overall_rating,
                comparable_cash_price=item.comparable_cash_price,
                selected_insurance_price_min=item.negotiated_price_min,
                selected_insurance_price_max=item.negotiated_price_max,
                selected_payer_name=item.selected_payer_name,
                selected_plan_name=item.selected_plan_name,
                published_payer_rate_count=item.matching_negotiated_rate_count,
                billing_scope=item.primary_billing_scope,
                setting=item.primary_service_setting,
                comparability=item.comparability_status,
                savings_difference=item.published_price_difference,
                savings_basis=item.difference_basis,
                service_availability_state=(
                    "published_price_found" if item.price_available else "unknown"
                ),
                additional_published_prices=item.additional_published_prices,
                sources=sources,
            )
        )
    limitations = [
        "Published prices are not personalized estimates; final cost may differ.",
        "A published insurer price does not confirm coverage or network participation.",
        "Service availability has not been independently verified.",
    ]
    origin = intent.zip or (
        f"{intent.city}, {intent.state}" if intent.city and intent.state else intent.location_text
    )
    return CareveroAIContext(
        procedure_slug=comparison.procedure_slug,
        procedure_name=comparison.procedure_name,
        search_origin=origin,
        radius_miles=intent.radius_miles,
        payer_name=intent.payer_name,
        plan_name=intent.plan_text,
        facilities=facilities,
        limitations=limitations,
    )
