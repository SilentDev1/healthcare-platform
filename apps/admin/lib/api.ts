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

export function formatDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
}
