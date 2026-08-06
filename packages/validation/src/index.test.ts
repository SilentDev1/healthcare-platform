import { describe, expect, it } from "vitest";

import { stateCode } from "./index.js";

describe("stateCode", () => {
  it("normalizes two-character state codes", () => {
    expect(stateCode.parse("nh")).toBe("NH");
  });

  it("rejects invalid codes", () => {
    expect(() => stateCode.parse("New Hampshire")).toThrow();
  });
});
