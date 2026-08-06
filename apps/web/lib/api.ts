const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return (await response.json()) as T;
}

export interface Location {
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
