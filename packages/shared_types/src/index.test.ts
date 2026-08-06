import { describe, expect, it } from "vitest";

import type { Facility } from "./index.js";

describe("Facility", () => {
  it("accepts the public contract", () => {
    const facility: Facility = {
      id: "facility-id",
      cms_certification_number: "300001",
      display_name: "Example Hospital",
      active: true,
    };
    expect(facility.active).toBe(true);
  });
});
