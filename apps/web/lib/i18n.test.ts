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

  it("preserves every placeholder token across all locales", () => {
    // Dynamic messages are parameterized, never English fragment concatenation.
    // A translation that drops or renames a {token} would break interpolation,
    // so every locale must carry exactly the same placeholder set per key.
    const tokensOf = (value: string) =>
      (value.match(/\{[a-zA-Z]+\}/g) ?? []).sort();
    for (const key of Object.keys(messages.en) as Array<
      keyof typeof messages.en
    >) {
      const englishTokens = tokensOf(messages.en[key]);
      for (const locale of locales) {
        expect(
          tokensOf(messages[locale][key]),
          `Locale "${locale}" key "${String(key)}" must keep tokens ${englishTokens.join(", ") || "(none)"}`,
        ).toEqual(englishTokens);
      }
    }
  });

  it("never renders a published rate as accepted or covered insurance", () => {
    // Consumer-language truthfulness guard (docs/consumer-language-glossary.md).
    const forbidden = [
      "insurance accepted",
      "accepts insurance",
      "in-network",
      "in network guarantee",
    ];
    for (const locale of locales) {
      for (const value of Object.values(messages[locale])) {
        for (const phrase of forbidden) {
          expect(value.toLowerCase()).not.toContain(phrase);
        }
      }
    }
  });
});
