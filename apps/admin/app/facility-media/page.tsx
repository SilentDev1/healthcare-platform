import {
  apiGet,
  formatDate,
  type FacilityMediaPage,
} from "../../lib/api";

export default async function FacilityMediaReviewPage() {
  try {
    const data = await apiGet<FacilityMediaPage>(
      "/api/v1/admin/facility-media?page_size=100",
    );
    const counts = data.status_counts ?? {};
    return (
      <main>
        <h1>Facility media review</h1>
        <p>
          Verified images are the only ones shown publicly. Verify / reject /
          set-primary are auditable actions run via{" "}
          <code>scripts.facility_media</code> (records verified_by + notes). See{" "}
          <code>docs/FACILITY_MEDIA_POLICY.md</code>.
        </p>
        <p>
          {["pending", "verified", "rejected", "broken"].map((status) => (
            <span key={status} style={{ marginRight: "1.5rem" }}>
              <strong>{status}:</strong> {counts[status] ?? 0}
            </span>
          ))}
        </p>
        {data.items.length === 0 ? (
          <p>No facility media recorded yet. Discover candidates with the CLI.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Preview</th>
                  <th>Facility</th>
                  <th>Status</th>
                  <th>Primary</th>
                  <th>Source / license</th>
                  <th>Attribution</th>
                  <th>Size</th>
                  <th>Added</th>
                  <th>Media id</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={item.image_url}
                          alt=""
                          loading="lazy"
                          style={{
                            width: 96,
                            height: 64,
                            objectFit: "cover",
                            borderRadius: 4,
                          }}
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>{item.facility_name}</td>
                    <td>{item.verification_status}</td>
                    <td>{item.is_primary ? "★" : ""}</td>
                    <td>
                      {item.source_url ? (
                        <a href={item.source_url} target="_blank" rel="noreferrer">
                          {item.source_type}
                        </a>
                      ) : (
                        item.source_type
                      )}
                      <br />
                      {item.license_type ?? "no license recorded"}
                    </td>
                    <td>{item.attribution_text ?? "—"}</td>
                    <td>
                      {item.width && item.height
                        ? `${item.width}×${item.height}`
                        : "—"}
                    </td>
                    <td>{formatDate(item.created_at)}</td>
                    <td>
                      <code>{item.id}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>Facility media review</h1>
        <p className="error" role="alert">
          Unable to load facility media:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}
