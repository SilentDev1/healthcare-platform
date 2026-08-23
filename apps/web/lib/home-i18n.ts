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
      "Now live in New Hampshire and Massachusetts, with more of New England coming soon.",
    statusLive: "Live",
    statusNext: "Next",
    mapAria:
      "Map of New England. New Hampshire is live with verified provider data; other states are coming soon.",
  },
  es: {
    eyebrow: "Precios de salud, con claridad",
    expandTitle: "Carevero se expande por Nueva Inglaterra",
    expandBody:
      "Ahora disponible en New Hampshire y Massachusetts; pronto llegaremos a más de Nueva Inglaterra.",
    statusLive: "Activo",
    statusNext: "Próximo",
    mapAria:
      "Mapa de Nueva Inglaterra. New Hampshire está activo con datos de proveedores verificados; otros estados llegarán pronto.",
  },
  vi: {
    eyebrow: "Giá dịch vụ y tế, rõ ràng",
    expandTitle: "Carevero đang mở rộng khắp New England",
    expandBody:
      "Hiện đã có tại New Hampshire và Massachusetts; sẽ sớm mở rộng khắp New England.",
    statusLive: "Đang hoạt động",
    statusNext: "Sắp tới",
    mapAria:
      "Bản đồ New England. New Hampshire đang hoạt động với dữ liệu nhà cung cấp đã xác minh; các tiểu bang khác sắp có.",
  },
  "zh-CN": {
    eyebrow: "医疗价格，一目了然",
    expandTitle: "Carevero 正在向新英格兰扩展",
    expandBody: "现已在新罕布什尔州和马萨诸塞州上线，很快会覆盖更多新英格兰地区。",
    statusLive: "已上线",
    statusNext: "即将",
    mapAria:
      "新英格兰地图。新罕布什尔州已上线，提供已验证的提供者数据；其他州即将推出。",
  },
  "zh-TW": {
    eyebrow: "醫療價格，一目了然",
    expandTitle: "Carevero 正在向新英格蘭擴展",
    expandBody: "現已在新罕布夏州和麥薩諸塞州上線，很快會覆蓋更多新英格蘭地區。",
    statusLive: "已上線",
    statusNext: "即將",
    mapAria:
      "新英格蘭地圖。新罕布夏州已上線，提供已驗證的提供者資料；其他州即將推出。",
  },
};
