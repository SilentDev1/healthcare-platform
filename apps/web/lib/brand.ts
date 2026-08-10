export const brand = {
  name: "Carevero",
  logoText: "Carevero",
  tagline: "Healthcare prices, made clearer.",
  description: "Compare published hospital prices and quality information.",
} as const;

export const launchRegion = {
  state: "NH",
  name: "New Hampshire",
  coverageLabel: "statewide",
  mapCenter: [43.45, -71.56] as [number, number],
  mapZoom: 8,
} as const;
