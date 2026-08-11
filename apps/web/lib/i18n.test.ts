import { describe, expect, it } from "vitest";
import { localeNames, localePath, locales, messages } from "./i18n";

describe("consumer internationalization", () => {
  it("supports every active beta locale with complete common messages", () => {
    expect(locales).toEqual(["en", "es", "vi", "zh-TW", "zh-CN"]);
    const englishKeys = Object.keys(messages.en).sort();
    for (const locale of locales) {
      expect(localeNames[locale]).toBeTruthy();
      expect(Object.keys(messages[locale]).sort()).toEqual(englishKeys);
      expect(Object.values(messages[locale]).every(Boolean)).toBe(true);
    }
  });

  it("creates shareable localized routes without changing canonical identity", () => {
    const canonical =
      "/procedures/mri-knee-without-contrast/prices?payer=aetna";
    expect(localePath("en", canonical)).toBe(canonical);
    expect(localePath("vi", canonical)).toBe(`/vi${canonical}`);
    expect(localePath("zh-TW", canonical)).toBe(`/zh-TW${canonical}`);
  });

  it("preserves reviewed Vietnamese and independent Chinese characters", () => {
    expect(messages.vi.heroAccent).toContain("Rõ ràng");
    expect(messages["zh-TW"].procedures).toBe("醫療項目");
    expect(messages["zh-CN"].procedures).toBe("医疗项目");
  });
});
