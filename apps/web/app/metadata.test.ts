import { describe, expect, it } from "vitest";
import { metadata as rootMetadata, seoRobots } from "./layout";
import robots from "./robots";
import { brand } from "../lib/brand";

describe("public brand and SEO safety", () => {
  it("uses Carevero metadata consistently", () => {
    expect(brand.name).toBe("Carevero");
    expect(JSON.stringify(rootMetadata)).toContain("Carevero");
    expect(JSON.stringify(rootMetadata)).not.toContain("CareCompare");
  });

  it("keeps query and comparison pages out of the index", () => {
    const rules = robots().rules;
    expect(JSON.stringify(rules)).toContain("/compare");
    expect(JSON.stringify(rules)).toContain("/search?");
  });

  it("marks every page noindex during private beta", () => {
    expect(seoRobots("false")).toEqual({
      index: false,
      follow: false,
      nocache: true,
    });
    expect(seoRobots("true")).toBeUndefined();
  });
});
