import type { Locale } from "./i18n";

/**
 * Self-contained translations for the "Ask Carevero" experience (homepage entry + /ask page).
 * Kept separate from the giant flat `Messages` object so it never affects that type's key-parity
 * invariant. Every locale defines the same keys (enforced by `Record<Locale, AskStrings>`).
 *
 * The model's intent is language-independent (resolved server-side); only the SHELL is localized.
 * Proper names / provider names are never machine-translated here.
 */

export interface AskStrings {
  navLabel: string;
  // Homepage compact entry point
  homeHeading: string;
  homeSubhead: string;
  homePlaceholder: string;
  homeCta: string;
  // Secondary manual-search disclosure on the homepage hero
  homeManualPrompt: string;
  homeManualCta: string;
  // /ask page
  title: string;
  subtitle: string;
  safety: string;
  placeholder: string;
  send: string;
  starters: string[];
  loading: string;
  // Response states
  medicalBoundary: string;
  medicalFollowup: string;
  outOfScope: string;
  fallback: string;
  error: string;
  noResults: string;
  // Result labels
  labelService: string;
  labelLocation: string;
  labelResults: string;
  labelPrices: string;
  priceNotAvailable: string;
  viewLocation: string;
  viewDetails: string;
  compare: string;
  // privacy hint
  privacyHint: string;
  you: string;
  assistant: string;
}

export const askMessages: Record<Locale, AskStrings> = {
  en: {
    navLabel: "Ask Carevero",
    homeHeading: "Ask Carevero",
    homeSubhead: "What are you looking for?",
    homePlaceholder: "Ask about an MRI, blood test, procedure, provider, or price…",
    homeCta: "Ask Carevero",
    homeManualPrompt: "Rather search manually?",
    homeManualCta: "Search prices",
    title: "Ask Carevero",
    subtitle:
      "Get help finding and understanding Carevero’s healthcare price and provider information.",
    safety:
      "Carevero helps you find and understand healthcare pricing and provider information. It does not provide medical advice, diagnosis, or treatment recommendations.",
    placeholder: "Ask about a procedure, price, hospital, lab, or provider…",
    send: "Send",
    starters: [
      "Compare MRI prices",
      "Find labs near Nashua",
      "Which locations have prices for a CBC?",
      "Find urgent care near Nashua",
      "What does discounted cash price mean?",
    ],
    loading: "Finding Carevero information…",
    medicalBoundary:
      "Carevero can help compare prices and locations once you know which test or service you need. A healthcare professional can determine which test is appropriate for your symptoms.",
    medicalFollowup:
      "If you already have an order for an MRI, CT scan, or X-ray, I can help you compare locations and published prices.",
    outOfScope:
      "I can help with healthcare services, providers, published prices, and using Carevero.",
    fallback:
      "Here is what Carevero found from a direct search of its verified data.",
    error:
      "Something went wrong. Here is a direct Carevero search instead.",
    noResults:
      "Carevero didn’t find a match. Try a procedure, provider, location, or category.",
    labelService: "Service",
    labelLocation: "Location",
    labelResults: "Places to compare",
    labelPrices: "Published prices",
    priceNotAvailable: "Published price not currently available in Carevero",
    viewLocation: "View location",
    viewDetails: "View details",
    compare: "Compare",
    privacyHint:
      "Please don’t enter personal or medical-record details — just the procedure, provider, or location.",
    you: "You",
    assistant: "Carevero",
  },
  es: {
    navLabel: "Preguntar a Carevero",
    homeHeading: "Preguntar a Carevero",
    homeSubhead: "¿Qué está buscando?",
    homePlaceholder: "Pregunte por una resonancia, análisis de sangre, procedimiento, proveedor o precio…",
    homeCta: "Preguntar a Carevero",
    homeManualPrompt: "¿Prefiere buscar manualmente?",
    homeManualCta: "Buscar precios",
    title: "Preguntar a Carevero",
    subtitle:
      "Obtenga ayuda para encontrar y entender la información de precios y proveedores de Carevero.",
    safety:
      "Carevero le ayuda a encontrar y entender información sobre precios y proveedores de atención médica. No brinda consejo médico, diagnóstico ni recomendaciones de tratamiento.",
    placeholder: "Pregunte por un procedimiento, precio, hospital, laboratorio o proveedor…",
    send: "Enviar",
    starters: [
      "Comparar precios de MRI",
      "Buscar laboratorios cerca de Nashua",
      "¿Qué lugares tienen precios para un hemograma (CBC)?",
      "Buscar atención de urgencia cerca de Nashua",
      "¿Qué significa precio en efectivo con descuento?",
    ],
    loading: "Buscando información de Carevero…",
    medicalBoundary:
      "Carevero puede ayudarle a comparar precios y ubicaciones una vez que sepa qué prueba o servicio necesita. Un profesional de la salud puede determinar qué prueba es adecuada para sus síntomas.",
    medicalFollowup:
      "Si ya tiene una orden para una resonancia, tomografía o radiografía, puedo ayudarle a comparar ubicaciones y precios publicados.",
    outOfScope:
      "Puedo ayudar con servicios de salud, proveedores, precios publicados y el uso de Carevero.",
    fallback:
      "Esto es lo que Carevero encontró en una búsqueda directa de sus datos verificados.",
    error: "Algo salió mal. Aquí tiene una búsqueda directa de Carevero.",
    noResults:
      "Carevero no encontró una coincidencia. Pruebe con un procedimiento, proveedor, ubicación o categoría.",
    labelService: "Servicio",
    labelLocation: "Ubicación",
    labelResults: "Lugares para comparar",
    labelPrices: "Precios publicados",
    priceNotAvailable: "Precio publicado no disponible actualmente en Carevero",
    viewLocation: "Ver ubicación",
    viewDetails: "Ver detalles",
    compare: "Comparar",
    privacyHint:
      "No ingrese datos personales ni de su historial médico; solo el procedimiento, proveedor o ubicación.",
    you: "Usted",
    assistant: "Carevero",
  },
  vi: {
    navLabel: "Hỏi Carevero",
    homeHeading: "Hỏi Carevero",
    homeSubhead: "Bạn đang tìm gì?",
    homePlaceholder: "Hỏi về MRI, xét nghiệm máu, thủ thuật, nhà cung cấp hoặc giá…",
    homeCta: "Hỏi Carevero",
    homeManualPrompt: "Muốn tự tìm kiếm?",
    homeManualCta: "Tìm giá",
    title: "Hỏi Carevero",
    subtitle:
      "Nhận trợ giúp tìm và hiểu thông tin về giá và nhà cung cấp dịch vụ y tế của Carevero.",
    safety:
      "Carevero giúp bạn tìm và hiểu thông tin về giá và nhà cung cấp dịch vụ y tế. Carevero không đưa ra lời khuyên y tế, chẩn đoán hoặc đề xuất điều trị.",
    placeholder: "Hỏi về một thủ thuật, giá, bệnh viện, phòng xét nghiệm hoặc nhà cung cấp…",
    send: "Gửi",
    starters: [
      "So sánh giá MRI",
      "Tìm phòng xét nghiệm gần Nashua",
      "Những địa điểm nào có giá cho xét nghiệm CBC?",
      "Tìm cơ sở cấp cứu nhanh gần Nashua",
      "Giá tiền mặt được giảm nghĩa là gì?",
    ],
    loading: "Đang tìm thông tin Carevero…",
    medicalBoundary:
      "Carevero có thể giúp so sánh giá và địa điểm khi bạn đã biết cần xét nghiệm hoặc dịch vụ nào. Chuyên gia y tế có thể xác định xét nghiệm nào phù hợp với triệu chứng của bạn.",
    medicalFollowup:
      "Nếu bạn đã có chỉ định chụp MRI, CT hoặc X-quang, tôi có thể giúp so sánh địa điểm và giá đã công bố.",
    outOfScope:
      "Tôi có thể giúp về dịch vụ y tế, nhà cung cấp, giá đã công bố và cách dùng Carevero.",
    fallback:
      "Đây là những gì Carevero tìm thấy khi tìm kiếm trực tiếp trong dữ liệu đã xác minh.",
    error: "Đã có lỗi xảy ra. Đây là kết quả tìm kiếm trực tiếp của Carevero.",
    noResults:
      "Carevero không tìm thấy kết quả phù hợp. Hãy thử một thủ thuật, nhà cung cấp, địa điểm hoặc danh mục.",
    labelService: "Dịch vụ",
    labelLocation: "Địa điểm",
    labelResults: "Nơi để so sánh",
    labelPrices: "Giá đã công bố",
    priceNotAvailable: "Giá công bố hiện chưa có trong Carevero",
    viewLocation: "Xem địa điểm",
    viewDetails: "Xem chi tiết",
    compare: "So sánh",
    privacyHint:
      "Vui lòng không nhập thông tin cá nhân hoặc hồ sơ bệnh án — chỉ cần thủ thuật, nhà cung cấp hoặc địa điểm.",
    you: "Bạn",
    assistant: "Carevero",
  },
  "zh-CN": {
    navLabel: "询问 Carevero",
    homeHeading: "询问 Carevero",
    homeSubhead: "您在找什么？",
    homePlaceholder: "询问 MRI、血液检查、项目、提供者或价格…",
    homeCta: "询问 Carevero",
    homeManualPrompt: "想手动搜索？",
    homeManualCta: "搜索价格",
    title: "询问 Carevero",
    subtitle: "获取帮助，查找并理解 Carevero 的医疗价格与提供者信息。",
    safety:
      "Carevero 帮助您查找并理解医疗价格与提供者信息。它不提供医疗建议、诊断或治疗建议。",
    placeholder: "询问某项目、价格、医院、化验室或提供者…",
    send: "发送",
    starters: [
      "比较 MRI 价格",
      "查找 Nashua 附近的化验室",
      "哪些地点有 CBC（全血细胞计数）的价格？",
      "查找 Nashua 附近的紧急护理",
      "折扣现金价是什么意思？",
    ],
    loading: "正在查找 Carevero 信息…",
    medicalBoundary:
      "一旦您知道需要哪项检查或服务，Carevero 就能帮助比较价格和地点。医疗专业人员可以判断哪项检查适合您的症状。",
    medicalFollowup:
      "如果您已经有 MRI、CT 或 X 光的医嘱，我可以帮助比较地点和已公布的价格。",
    outOfScope: "我可以帮助您了解医疗服务、提供者、已公布的价格以及 Carevero 的使用。",
    fallback: "以下是 Carevero 在其已验证数据中直接搜索到的结果。",
    error: "出现了问题。以下是 Carevero 的直接搜索结果。",
    noResults: "Carevero 未找到匹配项。请尝试项目、提供者、地点或类别。",
    labelService: "服务",
    labelLocation: "地点",
    labelResults: "可比较的地点",
    labelPrices: "已公布价格",
    priceNotAvailable: "Carevero 目前暂无已公布价格",
    viewLocation: "查看地点",
    viewDetails: "查看详情",
    compare: "比较",
    privacyHint: "请勿输入个人或病历信息——只需项目、提供者或地点即可。",
    you: "您",
    assistant: "Carevero",
  },
  "zh-TW": {
    navLabel: "詢問 Carevero",
    homeHeading: "詢問 Carevero",
    homeSubhead: "您在找什麼？",
    homePlaceholder: "詢問 MRI、血液檢查、項目、提供者或價格…",
    homeCta: "詢問 Carevero",
    homeManualPrompt: "想手動搜尋？",
    homeManualCta: "搜尋價格",
    title: "詢問 Carevero",
    subtitle: "取得協助，尋找並瞭解 Carevero 的醫療價格與提供者資訊。",
    safety:
      "Carevero 協助您尋找並瞭解醫療價格與提供者資訊。它不提供醫療建議、診斷或治療建議。",
    placeholder: "詢問某項目、價格、醫院、化驗室或提供者…",
    send: "傳送",
    starters: [
      "比較 MRI 價格",
      "尋找 Nashua 附近的化驗室",
      "哪些地點有 CBC（全血細胞計數）的價格？",
      "尋找 Nashua 附近的緊急護理",
      "折扣現金價是什麼意思？",
    ],
    loading: "正在尋找 Carevero 資訊…",
    medicalBoundary:
      "一旦您知道需要哪項檢查或服務，Carevero 就能協助比較價格和地點。醫療專業人員可以判斷哪項檢查適合您的症狀。",
    medicalFollowup:
      "如果您已經有 MRI、CT 或 X 光的醫囑，我可以協助比較地點和已公布的價格。",
    outOfScope: "我可以協助您瞭解醫療服務、提供者、已公布的價格以及 Carevero 的使用。",
    fallback: "以下是 Carevero 在其已驗證資料中直接搜尋到的結果。",
    error: "發生了問題。以下是 Carevero 的直接搜尋結果。",
    noResults: "Carevero 未找到相符項目。請嘗試項目、提供者、地點或類別。",
    labelService: "服務",
    labelLocation: "地點",
    labelResults: "可比較的地點",
    labelPrices: "已公布價格",
    priceNotAvailable: "Carevero 目前尚無已公布價格",
    viewLocation: "查看地點",
    viewDetails: "查看詳情",
    compare: "比較",
    privacyHint: "請勿輸入個人或病歷資訊——只需項目、提供者或地點即可。",
    you: "您",
    assistant: "Carevero",
  },
};
