import { headers } from "next/headers";
import { isLocale, messages, type Locale } from "./i18n";

export async function requestLocale(): Promise<Locale> {
  try {
    const value = (await headers()).get("x-carevero-locale") ?? "en";
    return isLocale(value) ? value : "en";
  } catch {
    // Component unit tests do not create a Next request scope.
    return "en";
  }
}

export async function requestMessages() {
  return messages[await requestLocale()] ?? messages.en;
}
