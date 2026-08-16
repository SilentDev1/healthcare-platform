const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public status: number) {
    super(`API request failed (${status})`);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status);
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
  cms_certification_number: string | null;
  display_name: string;
  legal_name: string;
  facility_type: string | null;
  ownership_type: string | null;
  phone: string | null;
  website_url: string | null;
  updated_at: string;
  locations: Location[];
  organization_name?: string | null;
  organization_type?: string | null;
  capabilities?: string[];
  is_hospital?: boolean;
  image_url?: string | null;
  image_alt?: string | null;
  image_attribution?: string | null;
  image_source?: string | null;
}
export interface DirectoryFacility {
  id: string;
  cms_certification_number: string | null;
  display_name: string;
  city: string | null;
  state: string | null;
  facility_type: string | null;
  published_procedure_count: number;
  pricing_status: string;
  price_available: boolean;
  cms_overall_rating: string | null;
  organization_name?: string | null;
  organization_type?: string | null;
  location_type?: string | null;
  region?: string | null;
  capabilities: string[];
  image_url?: string | null;
  image_alt?: string | null;
  image_attribution?: string | null;
  image_source?: string | null;
}
export interface DirectoryStateOption {
  code: string;
  name: string;
  facility_count: number;
}
export interface DirectoryCapabilityOption {
  capability: string;
  location_count: number;
}
export interface FacilityDirectory {
  items: DirectoryFacility[];
  page: number;
  page_size: number;
  total: number;
  total_states: number;
  states: DirectoryStateOption[];
  facility_types: string[];
  capabilities: DirectoryCapabilityOption[];
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
  metadata: {
    slug?: string;
    category?: string;
    procedure_count?: number;
    navigation_only?: boolean;
    // Provider-neutral capability-location results:
    capability?: string;
    facility_location_id?: string;
    location_type?: string;
    organization_name?: string | null;
    organization_type?: string | null;
    region?: string | null;
  };
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
export interface ProcedureCategory {
  id: string;
  parent_id: string | null;
  slug: string;
  name: string;
  description: string;
  sort_order: number;
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

export interface FacilityProcedureOverviewItem {
  procedure_slug: string;
  procedure_name: string;
  facility_location_id: string;
  location_name: string | null;
  city: string;
  service_settings: string[];
  cash_price_min: string | null;
  cash_price_max: string | null;
  negotiated_price_min: string | null;
  negotiated_price_max: string | null;
  summary_count: number;
  latest_updated: string;
  source_url: string;
}

export interface FacilityProcedureOverview {
  facility_id: string;
  procedure_count: number;
  items: FacilityProcedureOverviewItem[];
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
  cash_price_value_count?: number;
  cash_price_record_count?: number;
  cash_price_explanation?: string | null;
  cash_price_reason_codes?: string[];
  image_url?: string | null;
  image_alt?: string | null;
  image_attribution?: string | null;
  image_source?: string | null;
  matching_negotiated_rate_count?: number;
  distinct_payer_count?: number;
  distinct_plan_count?: number;
  published_payers?: Array<{
    slug: string;
    name: string;
    rate_count: number;
    plan_count: number;
  }>;
  selected_payer_name?: string | null;
  selected_plan_name?: string | null;
  all_published_negotiated_min?: string | null;
  all_published_negotiated_max?: string | null;
  extreme_rate_spread?: boolean;
  data_completeness?: string;
  completeness_notes?: string[];
  service_settings: string[];
  summary_count: number;
  source_count: number;
  latest_updated: string | null;
  source_file_date?: string | null;
  source_file_last_modified?: string | null;
  downloaded_at?: string | null;
  imported_at?: string | null;
  carevero_refresh_date?: string | null;
  source_url: string | null;
  primary_service_setting?: string | null;
  primary_billing_scope?: string | null;
  comparability_status?: string;
  comparability_reason?: string | null;
  additional_published_prices?: Array<{
    service_setting: string;
    billing_scope: string;
    amount_min: string;
    amount_max: string;
  }>;
  distance_miles?: number | null;
  comparable_cash_price?: string | null;
  published_price_difference?: string | null;
  difference_basis?: string | null;
  is_lowest_comparable_cash?: boolean;
  comparable_cash_facility_count?: number;
  lower_priced_nearby_option?: {
    facility_id: string;
    facility_name: string;
    facility_location_id: string;
    comparable_cash_price: string | null;
    published_price_difference: string | null;
    distance_miles: number | null;
  } | null;
}

export interface ProcedureComparison {
  procedure_slug: string;
  procedure_name: string;
  state: string;
  active_facilities: number;
  facilities_with_prices: number;
  service_locations: number;
  origin_resolved?: boolean;
  items: ProcedureComparisonItem[];
}

export interface ConsumerPriceDetailRecord {
  semantic_type: string;
  amount: string;
  payer_slug: string | null;
  payer_name: string | null;
  plan_id: string | null;
  plan_name: string | null;
  negotiated_rate_type: string | null;
  original_description: string;
  billing_codes: Array<{
    system: string | null;
    code: string | null;
    modifier: string | null;
  }>;
  service_variant: string;
  service_setting: string;
  component_scope: string;
  source_row_identity: string;
  source_url: string;
  source_checksum_sha256: string;
  source_file_date: string | null;
  source_file_last_modified: string | null;
  downloaded_at: string;
  imported_at: string;
  carevero_refresh_date: string;
}

export interface ConsumerPriceDetail {
  procedure_slug: string;
  procedure_name: string;
  facility_id: string;
  facility_name: string;
  facility_location_id: string;
  location_name: string | null;
  records: ConsumerPriceDetailRecord[];
  records_truncated: boolean;
  disclaimer: string;
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
