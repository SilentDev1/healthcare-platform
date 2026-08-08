import {
  apiGet,
  type FacilityScore,
  type Page,
  type StatewideScorecard,
} from "../../lib/api";

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 80 ? "#087f5b" : value >= 50 ? "#e67700" : "#c92a2a";
  return (
    <div style={{ marginBottom: "0.5rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.85rem",
        }}
      >
        <span style={{ textTransform: "capitalize" }}>{label}</span>
        <span style={{ fontWeight: 700 }}>{value}%</span>
      </div>
      <div
        style={{
          background: "#e8efed",
          borderRadius: "0.25rem",
          height: "0.6rem",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            background: color,
            width: `${Math.max(2, value)}%`,
            height: "100%",
            borderRadius: "0.25rem",
          }}
        />
      </div>
    </div>
  );
}

export default async function ScorecardPage() {
  try {
    const [scorecard, facilityScores] = await Promise.all([
      apiGet<StatewideScorecard>("/api/v1/pricing/scorecard"),
      apiGet<Page<FacilityScore>>(
        "/api/v1/pricing/facility-scores?page_size=100&sort=overall_score",
      ),
    ]);

    return (
      <main>
        <p className="eyebrow">INTERNAL ONLY</p>
        <h1>Statewide Readiness Scorecard</h1>

        {/* Readiness gauge */}
        <section className="panel" style={{ textAlign: "center" }}>
          <div
            style={{
              fontSize: "3rem",
              fontWeight: 700,
              color: scorecard.meets_target ? "#087f5b" : "#e67700",
            }}
          >
            {scorecard.overall_readiness}%
          </div>
          <div className="muted">
            Target: {scorecard.target}% ·{" "}
            {scorecard.meets_target ? "TARGET MET" : "BELOW TARGET"}
          </div>
        </section>

        {/* Component score bars */}
        <section className="panel" style={{ marginTop: "1rem" }}>
          <h2>Component scores</h2>
          {Object.entries(scorecard.component_scores).map(([name, score]) => (
            <ScoreBar key={name} label={name} value={score} />
          ))}
        </section>

        {/* Per-facility table sorted by worst first */}
        <h2 style={{ marginTop: "2rem" }}>
          Per-facility scores ({facilityScores.total} facilities)
        </h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Facility</th>
                <th>City</th>
                <th>Overall</th>
                <th>Discovery</th>
                <th>Download</th>
                <th>Parse</th>
                <th>Mapping</th>
                <th>Anomaly</th>
                <th>Freshness</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {facilityScores.items.map((f) => (
                <tr key={f.facility_id}>
                  <td>{f.facility_name}</td>
                  <td>{f.city ?? "—"}</td>
                  <td>
                    <strong
                      style={{
                        color:
                          f.overall_score >= 80
                            ? "#087f5b"
                            : f.overall_score >= 50
                              ? "#e67700"
                              : "#c92a2a",
                      }}
                    >
                      {Math.round(f.overall_score)}%
                    </strong>
                  </td>
                  <td>{Math.round(f.source_discovery_score)}</td>
                  <td>{Math.round(f.download_score)}</td>
                  <td>{Math.round(f.parse_score)}</td>
                  <td>{Math.round(f.mapping_score)}</td>
                  <td>{Math.round(f.anomaly_score)}</td>
                  <td>{Math.round(f.freshness_score)}</td>
                  <td>{Math.round(f.price_coverage_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>Statewide Scorecard</h1>
        <p className="error" role="alert">
          Unable to load scorecard:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}
