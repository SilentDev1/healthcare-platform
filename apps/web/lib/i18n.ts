export const locales = ["en", "es", "vi", "zh-TW", "zh-CN"] as const;
export type Locale = (typeof locales)[number];

export const localeNames: Record<Locale, string> = {
  en: "English",
  es: "Español",
  vi: "Tiếng Việt",
  "zh-TW": "繁體中文",
  "zh-CN": "简体中文",
};

const en = {
  skip: "Skip to main content",
  mainNavigation: "Main navigation",
  findPrices: "Find prices",
  hospitals: "Hospitals",
  procedures: "Procedures",
  map: "Map",
  howItWorks: "How it works",
  language: "Language",
  aboutData: "About the data",
  privacy: "Privacy",
  terms: "Terms & disclaimers",
  footerDisclaimer:
    "Published hospital prices are estimates for comparison, not a quote or guarantee. Verify costs and network participation with your hospital and insurer.",
  eyebrow: "Clear information for confident choices",
  heroTitle: "Healthcare prices.",
  heroAccent: "Clear. Local. Comparable.",
  heroBody:
    "Compare published prices for procedures and services at New Hampshire hospitals. Review pricing, location, and available CMS quality information before choosing care.",
  free: "Free to use",
  noAccount: "No account required",
  publishedData: "Published hospital data",
  popular: "Popular searches",
  compareServiceLocations: "Compare service locations",
  location: "Location",
  coverage: "Coverage",
  selfPay: "Self-pay",
  chooseInsurance: "Choose insurance",
  insurance: "Insurance (published rates)",
  planOptional: "Insurance plan (optional)",
  matchingRates: "Published matching negotiated rates",
  networkNotice:
    "A published negotiated rate does not guarantee network participation or coverage.",
  priceDetails: "View price details",
  viewAllProcedures: "View all procedures",
};

export type Messages = typeof en;

export const messages: Record<Locale, Messages> = {
  en,
  es: {
    skip: "Saltar al contenido principal",
    mainNavigation: "Navegación principal",
    findPrices: "Buscar precios",
    hospitals: "Hospitales",
    procedures: "Procedimientos",
    map: "Mapa",
    howItWorks: "Cómo funciona",
    language: "Idioma",
    aboutData: "Acerca de los datos",
    privacy: "Privacidad",
    terms: "Términos y avisos",
    footerDisclaimer:
      "Los precios publicados por hospitales son estimaciones para comparar, no una cotización ni garantía. Confirme los costos y la red con el hospital y su aseguradora.",
    eyebrow: "Información clara para decidir con confianza",
    heroTitle: "Precios de atención médica.",
    heroAccent: "Claros. Locales. Comparables.",
    heroBody:
      "Compare precios publicados de procedimientos y servicios en hospitales de New Hampshire. Revise precios, ubicación y la información de calidad disponible de CMS antes de elegir atención.",
    free: "Uso gratuito",
    noAccount: "No se requiere cuenta",
    publishedData: "Datos publicados por hospitales",
    popular: "Búsquedas populares",
    compareServiceLocations: "Comparar centros de atención",
    location: "Ubicación",
    coverage: "Cobertura",
    selfPay: "Pago por cuenta propia",
    chooseInsurance: "Elegir seguro",
    insurance: "Seguro (tarifas publicadas)",
    planOptional: "Plan de seguro (opcional)",
    matchingRates: "Tarifas negociadas publicadas coincidentes",
    networkNotice:
      "Una tarifa negociada publicada no garantiza la participación en la red ni la cobertura.",
    priceDetails: "Ver detalles del precio",
    viewAllProcedures: "Ver todos los procedimientos",
  },
  vi: {
    skip: "Chuyển đến nội dung chính",
    mainNavigation: "Điều hướng chính",
    findPrices: "Tìm giá",
    hospitals: "Bệnh viện",
    procedures: "Dịch vụ y tế",
    map: "Bản đồ",
    howItWorks: "Cách hoạt động",
    language: "Ngôn ngữ",
    aboutData: "Về dữ liệu",
    privacy: "Quyền riêng tư",
    terms: "Điều khoản và lưu ý",
    footerDisclaimer:
      "Giá bệnh viện công bố chỉ dùng để so sánh, không phải báo giá hay bảo đảm. Hãy xác nhận chi phí và tình trạng trong mạng lưới với bệnh viện và hãng bảo hiểm.",
    eyebrow: "Thông tin rõ ràng để tự tin lựa chọn",
    heroTitle: "Giá dịch vụ y tế.",
    heroAccent: "Rõ ràng. Gần bạn. Dễ so sánh.",
    heroBody:
      "So sánh giá bệnh viện tại New Hampshire đã công bố cho các thủ thuật và dịch vụ. Xem giá, địa điểm và thông tin chất lượng CMS hiện có trước khi chọn nơi chăm sóc.",
    free: "Miễn phí sử dụng",
    noAccount: "Không cần tài khoản",
    publishedData: "Dữ liệu bệnh viện công bố",
    popular: "Tìm kiếm phổ biến",
    compareServiceLocations: "So sánh các địa điểm dịch vụ",
    location: "Địa điểm",
    coverage: "Bảo hiểm",
    selfPay: "Tự thanh toán",
    chooseInsurance: "Chọn bảo hiểm",
    insurance: "Bảo hiểm (mức giá đã công bố)",
    planOptional: "Chương trình bảo hiểm (không bắt buộc)",
    matchingRates: "Mức giá thương lượng phù hợp đã công bố",
    networkNotice:
      "Mức giá thương lượng đã công bố không bảo đảm tình trạng trong mạng lưới hoặc quyền lợi được chi trả.",
    priceDetails: "Xem chi tiết giá",
    viewAllProcedures: "Xem tất cả dịch vụ",
  },
  "zh-TW": {
    skip: "跳至主要內容",
    mainNavigation: "主要導覽",
    findPrices: "查詢價格",
    hospitals: "醫院",
    procedures: "醫療項目",
    map: "地圖",
    howItWorks: "使用方式",
    language: "語言",
    aboutData: "關於資料",
    privacy: "隱私權",
    terms: "條款與免責聲明",
    footerDisclaimer:
      "醫院公布的價格僅供比較，並非報價或保證。請向醫院及保險公司確認費用與網絡資格。",
    eyebrow: "清楚資訊，安心選擇",
    heroTitle: "醫療服務價格。",
    heroAccent: "清楚。在地。可比較。",
    heroBody:
      "比較 New Hampshire 醫院公布的醫療項目與服務價格。選擇照護前，可查看價格、地點及現有的 CMS 品質資訊。",
    free: "免費使用",
    noAccount: "無需帳戶",
    publishedData: "醫院公布資料",
    popular: "熱門搜尋",
    compareServiceLocations: "比較服務地點",
    location: "地點",
    coverage: "保險資訊",
    selfPay: "自費",
    chooseInsurance: "選擇保險",
    insurance: "保險（已公布費率）",
    planOptional: "保險方案（選填）",
    matchingRates: "符合條件的已公布協議費率",
    networkNotice: "已公布的協議費率不保證網絡資格或承保範圍。",
    priceDetails: "查看價格詳情",
    viewAllProcedures: "查看所有醫療項目",
  },
  "zh-CN": {
    skip: "跳至主要内容",
    mainNavigation: "主导航",
    findPrices: "查询价格",
    hospitals: "医院",
    procedures: "医疗项目",
    map: "地图",
    howItWorks: "使用方式",
    language: "语言",
    aboutData: "关于数据",
    privacy: "隐私",
    terms: "条款与免责声明",
    footerDisclaimer:
      "医院公布的价格仅供比较，并非报价或保证。请向医院和保险公司确认费用与网络资格。",
    eyebrow: "信息清楚，选择更安心",
    heroTitle: "医疗服务价格。",
    heroAccent: "清楚。本地。可比较。",
    heroBody:
      "比较 New Hampshire 医院公布的医疗项目和服务价格。选择医疗服务前，可查看价格、地点和现有的 CMS 质量信息。",
    free: "免费使用",
    noAccount: "无需账户",
    publishedData: "医院公布数据",
    popular: "热门搜索",
    compareServiceLocations: "比较服务地点",
    location: "地点",
    coverage: "保险信息",
    selfPay: "自费",
    chooseInsurance: "选择保险",
    insurance: "保险（已公布费率）",
    planOptional: "保险计划（选填）",
    matchingRates: "符合条件的已公布协议费率",
    networkNotice: "已公布的协议费率不保证网络资格或承保范围。",
    priceDetails: "查看价格详情",
    viewAllProcedures: "查看所有医疗项目",
  },
};

export function isLocale(value: string | undefined): value is Locale {
  return locales.includes(value as Locale);
}

export function localePath(locale: Locale, path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return locale === "en"
    ? normalized
    : `/${locale}${normalized === "/" ? "" : normalized}`;
}
