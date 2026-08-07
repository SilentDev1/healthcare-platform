const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return (await response.json()) as T;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}
export interface AdminFacility {
  id: string;
  display_name: string;
  city: string | null;
  state: string | null;
  cms_certification_number: string;
  facility_type: string | null;
  active: boolean;
  latest_source_name: string;
  quality_measure_count: number;
  updated_at: string;
}
export interface ImportRun {
  id: string;
  importer_name: string;
  status: string;
  source_name: string;
  started_at: string;
  finished_at: string | null;
  rows_read: number;
  rows_inserted: number;
  rows_updated: number;
  rows_rejected: number;
  error_summary: string | null;
}
export interface SourceFile {
  id: string;
  source_name: string;
  source_url: string;
  checksum_sha256: string;
  source_published_at: string | null;
  downloaded_at: string;
  parser_version: string;
  status: string;
}
export interface Unmatched {
  id: string;
  source_record_identifier: string;
  supplied_cms_certification_number: string | null;
  supplied_facility_name: string | null;
  reason_unmatched: string;
  source_file_id: string;
  review_status: string;
}
export interface QualityMeasure {
  id: string;
  cms_measure_id: string;
  measure_name: string;
  category: string;
  unit: string | null;
  directionality: string;
}
export interface SearchResult {
  entity_type: string;
  entity_id: string;
  title: string;
  subtitle: string;
  score: number;
  match_reason: string;
  matched_term: string;
}
export interface Procedure {
  id: string;
  slug: string;
  consumer_name: string;
  service_setting: string;
  category: { name: string };
  aliases: string[];
}
export interface IdentityCandidate {
  id: string;
  supplied_name: string | null;
  supplied_identifiers: Record<string, unknown>;
  deterministic_method: string;
  score: string;
  reason: string;
  status: string;
}
export interface HealthEvaluation {
  id: string;
  rule_name: string;
  severity: string;
  entity_type: string;
  status: string;
  score: string;
  message: string;
}
export interface Pipeline {
  id: string;
  importer_name: string;
  source_type: string;
  current_status: string;
  freshness_status: string;
  latest_success_at: string | null;
  latest_failure_at: string | null;
  records_last_imported: number | null;
  error_summary: string | null;
}
export interface PricingCoverage {
  nh_facilities: number;
  facilities_with_sources: number;
  facilities_with_downloads: number;
  facilities_with_parsed_records: number;
  facilities_with_publishable_prices: number;
  publishable_procedures: number;
  last_updated: string | null;
}
export interface PricingAdminItem {
  id: string;
  data: Record<string, unknown>;
}

export function formatDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
}
