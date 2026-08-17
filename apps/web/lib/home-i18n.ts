import type { Locale } from "./i18n";

/**
 * Homepage-hero brand strings: the eyebrow, the New England expansion card, and
 * per-state live/next status. Kept out of the giant flat `Messages` object (which
 * enforces key-parity via `type Messages = typeof en`) so hero copy can evolve
 * without touching that invariant.
 *
 * Carevero is a NEW ENGLAND platform launching from New Hampshire — the copy here
 * is region-forward, never NH-only, and never claims a state is live before its
 * data passes production gates.
 */
export interface HomeStrings {
  eyebrow: string;
  expandTitle: string;
  expandBody: string;
  statusLive: string;
  statusNext: string;
  mapAria: string;
}

export const homeMessages: Record<Locale, HomeStrings> = {
  en: {
    eyebrow: "Healthcare prices, made clear",
    expandTitle: "Carevero is expanding across New England",
    expandBody:
      "We’re starting in New Hampshire and bringing verified price data to more states soon.",
    statusLive: "Live",
    statusNext: "Next",
    mapAria:
      "Map of New England. New Hampshire is live with verified provider data; other states are coming soon.",
  },
  es: {
    eyebrow: "Precios de salud, con claridad",
    expandTitle: "Carevero se expande por Nueva Inglaterra",
    expandBody:
      "Comenzamos en New Hampshire y pronto llevaremos datos de precios verificados a más estados.",
    statusLive: "Activo",
    statusNext: "Próximo",
    mapAria:
      "Mapa de Nueva Inglaterra. New Hampshire está activo con datos de proveedores verificados; otros estados llegarán pronto.",
  },
  vi: {
    eyebrow: "Giá dịch vụ y tế, rõ ràng",
    expandTitle: "Carevero đang mở rộng khắp New England",
    expandBody:
      "Chúng tôi bắt đầu từ New Hampshire và sẽ sớm mang dữ liệu giá đã xác minh đến nhiều tiểu bang hơn.",
    statusLive: "Đang hoạt động",
    statusNext: "Sắp tới",
    mapAria:
      "Bản đồ New England. New Hampshire đang hoạt động với dữ liệu nhà cung cấp đã xác minh; các tiểu bang khác sắp có.",
  },
  "zh-CN": {
    eyebrow: "医疗价格，一目了然",
    expandTitle: "Carevero 正在向新英格兰扩展",
    expandBody: "我们从新罕布什尔州起步，很快会将已验证的价格数据带到更多州。",
    statusLive: "已上线",
    statusNext: "即将",
    mapAria:
      "新英格兰地图。新罕布什尔州已上线，提供已验证的提供者数据；其他州即将推出。",
  },
  "zh-TW": {
    eyebrow: "醫療價格，一目了然",
    expandTitle: "Carevero 正在向新英格蘭擴展",
    expandBody: "我們從新罕布夏州起步，很快會將已驗證的價格資料帶到更多州。",
    statusLive: "已上線",
    statusNext: "即將",
    mapAria:
      "新英格蘭地圖。新罕布夏州已上線，提供已驗證的提供者資料；其他州即將推出。",
  },
};
