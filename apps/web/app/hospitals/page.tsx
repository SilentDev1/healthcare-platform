// Backward-compatible alias. /providers is the canonical consumer directory route;
// /hospitals keeps working (no broken inbound URLs) and renders the same directory.
export { default, metadata } from "../providers/page";
