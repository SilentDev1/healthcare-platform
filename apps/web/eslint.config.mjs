import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  ...nextVitals,
  { rules: { "react-hooks/error-boundaries": "off" } },
];

export default config;
