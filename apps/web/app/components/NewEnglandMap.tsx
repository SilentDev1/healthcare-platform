import { homeMessages } from "../../lib/home-i18n";
import { type Locale, type Messages } from "../../lib/i18n";

/**
 * Stylized New England regional map for the homepage hero — a lightweight, server-
 * rendered inline SVG (no map library, no client JS). It is the geographic brand
 * element: Carevero → New England, not Carevero → New Hampshire.
 *
 * HONESTY: New Hampshire is the only "live" state, drawn with a stronger fill and
 * illustrative coverage pins (verified NH providers exist across these areas). The
 * other five states are rendered as neutral expansion geography with NO provider
 * pins — a decorative marker is never made to look like a verified Carevero provider.
 * Massachusetts gets a subtle "next" outline only. No coverage numbers are hardcoded.
 */
export function NewEnglandMap({
  locale,
  t,
}: {
  locale: Locale;
  t: Messages;
}) {
  const h = homeMessages[locale] ?? homeMessages.en;
  const stateLabel = (code: string, fallback: string): string => {
    const key = `state${code}` as keyof Messages;
    const v = t[key];
    return typeof v === "string" ? v : fallback;
  };
  // Illustrative NH coverage points (within the live region only). Not specific
  // pinned providers — a brand representation that NH is live with verified data.
  const nhPins = [
    [322, 150],
    [332, 184],
    [314, 212],
    [336, 228],
    [320, 246],
  ];

  return (
    <div className="ne-map" role="group" aria-label={h.mapAria}>
      <svg
        viewBox="0 0 500 470"
        className="ne-map-svg"
        role="img"
        aria-label={h.mapAria}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="neOcean" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#dbeafe" />
            <stop offset="1" stopColor="#bfdbfe" />
          </linearGradient>
          <linearGradient id="neLive" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#2f7bf0" />
            <stop offset="1" stopColor="#0961dc" />
          </linearGradient>
          <filter id="nePin" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#1e3a8a" floodOpacity="0.35" />
          </filter>
          {/* Blue teardrop pin with a white medical cross — matches the brand marker. */}
          <g id="neProviderPin">
            <path
              d="M0,-13 C7.2,-13 12,-8 12,-1.5 C12,7 0,17 0,17 C0,17 -12,7 -12,-1.5 C-12,-8 -7.2,-13 0,-13 Z"
              fill="#0961dc"
              stroke="#ffffff"
              strokeWidth="1.5"
            />
            <path d="M0,-8 v9 M-4.5,-3.5 h9" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
          </g>
        </defs>

        <rect x="0" y="0" width="500" height="470" fill="url(#neOcean)" opacity="0.35" />

        {/* Expansion-geography states (neutral fill, thin white borders). */}
        <g className="ne-states" stroke="#ffffff" strokeWidth="2" strokeLinejoin="round">
          {/* Maine */}
          <path
            className="ne-state"
            d="M338,44 L398,32 L424,74 L432,150 L406,214 L372,250 L352,232 L360,182 L340,152 L336,96 Z"
            fill="#c4d7f2"
          />
          {/* Vermont */}
          <path
            className="ne-state"
            d="M250,108 L312,102 L306,178 L300,258 L256,252 L250,182 Z"
            fill="#cfe0f5"
          />
          {/* Massachusetts — subtle "next" treatment (dashed accent border). */}
          <path
            className="ne-state ne-state-next"
            d="M210,262 L306,258 L358,251 L394,266 L388,300 L360,315 L212,316 Z"
            fill="#c4d7f2"
          />
          {/* Connecticut */}
          <path
            className="ne-state"
            d="M212,320 L316,318 L322,364 L214,370 Z"
            fill="#cfe0f5"
          />
          {/* Rhode Island */}
          <path
            className="ne-state"
            d="M326,318 L356,315 L360,362 L330,364 Z"
            fill="#cfe0f5"
          />
          {/* New Hampshire — LIVE (stronger fill). */}
          <path
            className="ne-state ne-state-live"
            d="M312,102 L336,96 L360,182 L340,255 L308,260 L306,178 Z"
            fill="url(#neLive)"
          />
        </g>

        {/* State labels (not color-only: NH carries a Live tag, MA a Next tag). */}
        <g className="ne-labels" fontFamily="inherit">
          <text x="384" y="150" className="ne-label">
            {stateLabel("ME", "Maine")}
          </text>
          <text x="248" y="185" className="ne-label" textAnchor="middle">
            {stateLabel("VT", "Vermont")}
          </text>
          <text x="286" y="292" className="ne-label" textAnchor="middle">
            {stateLabel("MA", "Massachusetts")}
          </text>
          <text x="250" y="348" className="ne-label" textAnchor="middle">
            {stateLabel("CT", "Connecticut")}
          </text>
          <text x="343" y="336" className="ne-label ne-label-sm" textAnchor="middle">
            {stateLabel("RI", "Rhode Island")}
          </text>
          <text x="333" y="86" className="ne-label ne-label-nh" textAnchor="middle">
            {stateLabel("NH", "New Hampshire")}
          </text>
        </g>

        {/* NH coverage pins — live region only. */}
        <g filter="url(#nePin)">
          {nhPins.map(([x, y], i) => (
            <use key={i} href="#neProviderPin" x={x} y={y} />
          ))}
        </g>
      </svg>

      {/* Expansion card — honest status, no live-MA claim, no hardcoded counts. */}
      <div className="ne-expand-card">
        <span className="ne-expand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="22" height="22">
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path
              d="M3 12h18M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
            />
          </svg>
        </span>
        <div className="ne-expand-text">
          <p className="ne-expand-title">{h.expandTitle}</p>
          <p className="ne-expand-body">{h.expandBody}</p>
          <p className="ne-expand-status">
            <span className="ne-status ne-status-live">
              <span className="ne-status-dot" aria-hidden="true" />
              {stateLabel("NH", "New Hampshire")} — {h.statusLive}
            </span>
            <span className="ne-status ne-status-next">
              <span className="ne-status-dot" aria-hidden="true" />
              {stateLabel("MA", "Massachusetts")} — {h.statusNext}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
