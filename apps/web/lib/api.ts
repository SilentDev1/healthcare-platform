const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return (await response.json()) as T;
}

export interface Location {
  id: string;
  location_name: string | null;
  location_type: string;
  active: boolean;
  address_line_1: string;
  city: string;
  state: string;
  postal_code: string;
  county: string | null;
}
export interface Facility {
  id: string;
  cms_certification_number: string;
  display_name: string;
  legal_name: string;
  facility_type: string | null;
  ownership_type: string | null;
  phone: string | null;
  website_url: string | null;
  updated_at: string;
  locations: Location[];
}
export interface FacilityPage {
  items: Facility[];
  total: number;
}
export interface QualityPage {
  items: Array<{
    id: string;
    cms_measure_id: string;
    measure_name: string;
    category: string;
    score: string | null;
    footnote_code: string | null;
    reporting_period_end: string | null;
    source_file_id: string;
  }>;
  total: number;
}
export interface SearchResult {
  entity_type: string;
  entity_id: string;
  title: string;
  subtitle: string;
  location: string | null;
  score: number;
  match_reason: string;
  metadata: { slug?: string; category?: string };
}
export interface Procedure {
  id: string;
  slug: string;
  consumer_name: string;
  short_description: string;
  long_description: string;
  service_setting: string;
  complexity: string;
  shoppable: boolean;
  aliases: string[];
  category: { slug: string; name: string; description: string };
  billing_notice: string;
}
export interface PriceSummary {
  id: string;
  facility_id: string;
  facility_name: string;
  facility_location_id: string | null;
  location_name: string | null;
  location_type: string | null;
  address_line_1: string | null;
  city: string | null;
  procedure_slug: string;
  procedure_name: string;
  payer_name: string | null;
  plan_name: string | null;
  service_setting: string;
  cash_price_min: string | null;
  cash_price_max: string | null;
  negotiated_price_min: string | null;
  negotiated_price_max: string | null;
  source_url: string;
  last_updated: string;
  included_component_scope: string;
  disclaimer: string;
}
export interface PricePage {
  items: PriceSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProcedureComparisonItem {
  facility_id: string;
  facility_name: string;
  facility_location_id: string;
  location_name: string | null;
  location_type: string;
  address_line_1: string;
  city: string;
  state: string;
  postal_code: string;
  facility_type: string | null;
  cms_overall_rating: string | null;
  price_available: boolean;
  cash_price_min: string | null;
  cash_price_max: string | null;
  negotiated_price_min: string | null;
  negotiated_price_max: string | null;
  service_settings: string[];
  summary_count: number;
  source_count: number;
  latest_updated: string | null;
  source_url: string | null;
}

export interface ProcedureComparison {
  procedure_slug: string;
  procedure_name: string;
  state: string;
  active_facilities: number;
  facilities_with_prices: number;
  service_locations: number;
  items: ProcedureComparisonItem[];
}

export interface PricingHealth {
  facility_id: string;
  overall_score: number;
  source_discovery_score: number;
  download_score: number;
  parse_score: number;
  mapping_score: number;
  payer_normalization_score: number;
  anomaly_score: number;
  freshness_score: number;
  price_coverage_score: number;
  details: Record<string, unknown>;
  calculated_at: string;
}

export interface MapFeature {
  type: string;
  geometry: { type: string; coordinates: [number, number] };
  properties: {
    id: string;
    facility_id: string;
    name: string;
    location_name: string | null;
    city: string;
    pricing_status: string;
    procedure_count: number;
  };
}

export interface MapData {
  type: string;
  features: MapFeature[];
}

export interface SearchSuggestion {
  entity_type: string;
  entity_id: string;
  title: string;
  match_reason: string;
}
