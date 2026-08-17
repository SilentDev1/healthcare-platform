import type { Locale } from "./i18n";

/**
 * Self-contained translations for the consumer Provider Directory (/providers).
 * Kept out of the giant flat `Messages` object (which enforces key-parity via
 * `type Messages = typeof en`) so adding provider-directory copy never risks that
 * invariant. Every locale defines the same keys, enforced by `Record<Locale, DirectoryStrings>`.
 *
 * Provider-neutral by design: the directory holds hospitals AND non-hospital
 * providers (labs, urgent care, imaging, surgery centers, PT, etc.). Hospital-only
 * concepts (CMS ratings) are still labelled where they legitimately apply.
 */
export interface DirectoryStrings {
  navLabel: string;
  eyebrow: string;
  title: string;
  lede: string;
  free: string;
  noAccount: string;
  verifiedData: string;
  // Filter controls
  searchLabel: string;
  searchPlaceholder: string;
  search: string;
  providerType: string;
  allTypes: string;
  hasPrices: string;
  hasPricesAny: string;
  hasPricesYes: string;
  hasPricesNo: string;
  sortBy: string;
  sortNameAsc: string;
  sortNameDesc: string;
  clear: string;
  state: string;
  region: string;
  allRegions: string;
  allChip: string;
  more: string;
  // Views
  viewList: string;
  viewGrid: string;
  viewMap: string;
  // Result meta
  showing: string; // "Showing {from}–{to} of {total} locations"
  showingTyped: string; // "Showing {from}–{to} of {total} {type} locations"
  perPage: string; // "{count} per page"
  priceNotice: string;
  publishedPrices: string; // "Published prices for {count} procedures"
  publishedPricesOne: string;
  priceNotAvailable: string;
  cmsOverall: string;
  viewProvider: string;
  // Empty + pagination
  noResults: string;
  noResultsHelp: string;
  prev: string;
  next: string;
  pageOf: string; // "Page {page} of {total}"
  // Mobile drawer
  filters: string; // "Filters"
  applyFilters: string;
  closeFilters: string;
  // a11y
  viewSwitcherLabel: string;
  paginationLabel: string;
  filterRegionLabel: string;
  mapUnavailable: string;
  unavailableTitle: string;
  unavailable: string;
}

export const directoryMessages: Record<Locale, DirectoryStrings> = {
  en: {
    navLabel: "Providers",
    eyebrow: "Provider directory",
    title: "Find healthcare providers",
    lede: "Hospitals, labs, urgent care, imaging centers, surgery centers, physical therapy and more.",
    free: "Free to use",
    noAccount: "No account required",
    verifiedData: "Verified provider data",
    searchLabel: "Search providers",
    searchPlaceholder: "Search provider, city or ZIP",
    search: "Search",
    providerType: "Provider type",
    allTypes: "All types",
    hasPrices: "Has prices",
    hasPricesAny: "Any",
    hasPricesYes: "Published prices available",
    hasPricesNo: "Price not currently available",
    sortBy: "Sort by",
    sortNameAsc: "Name (A–Z)",
    sortNameDesc: "Name (Z–A)",
    clear: "Clear",
    state: "State",
    region: "Region",
    allRegions: "All regions",
    allChip: "All",
    more: "More",
    viewList: "List",
    viewGrid: "Grid",
    viewMap: "Map",
    showing: "Showing {from}–{to} of {total} locations",
    showingTyped: "Showing {from}–{to} of {total} {type} locations",
    perPage: "{count} per page",
    priceNotice: "Providers without published prices remain visible.",
    publishedPrices: "Published prices for {count} procedures",
    publishedPricesOne: "Published prices for {count} procedure",
    priceNotAvailable: "Published price not currently available in Carevero",
    cmsOverall: "CMS Overall Rating",
    viewProvider: "View provider",
    noResults: "No providers match these filters",
    noResultsHelp: "Try a different provider type, region, or clear the filters.",
    prev: "Previous",
    next: "Next",
    pageOf: "Page {page} of {total}",
    filters: "Filters",
    applyFilters: "Show results",
    closeFilters: "Close",
    viewSwitcherLabel: "Directory view",
    paginationLabel: "Provider directory pages",
    filterRegionLabel: "Filter by region",
    mapUnavailable: "The map could not be loaded. Switch to List or Grid to browse providers.",
    unavailableTitle: "Providers",
    unavailable: "Provider directory is temporarily unavailable.",
  },
  es: {
    navLabel: "Proveedores",
    eyebrow: "Directorio de proveedores",
    title: "Encuentre proveedores de salud",
    lede: "Hospitales, laboratorios, atención de urgencia, centros de imágenes, centros quirúrgicos, fisioterapia y más.",
    free: "Uso gratuito",
    noAccount: "Sin cuenta",
    verifiedData: "Datos de proveedores verificados",
    searchLabel: "Buscar proveedores",
    searchPlaceholder: "Buscar proveedor, ciudad o código postal",
    search: "Buscar",
    providerType: "Tipo de proveedor",
    allTypes: "Todos los tipos",
    hasPrices: "Con precios",
    hasPricesAny: "Cualquiera",
    hasPricesYes: "Con precios publicados",
    hasPricesNo: "Precio no disponible por ahora",
    sortBy: "Ordenar por",
    sortNameAsc: "Nombre (A–Z)",
    sortNameDesc: "Nombre (Z–A)",
    clear: "Limpiar",
    state: "Estado",
    region: "Región",
    allRegions: "Todas las regiones",
    allChip: "Todos",
    more: "Más",
    viewList: "Lista",
    viewGrid: "Cuadrícula",
    viewMap: "Mapa",
    showing: "Mostrando {from}–{to} de {total} ubicaciones",
    showingTyped: "Mostrando {from}–{to} de {total} ubicaciones de {type}",
    perPage: "{count} por página",
    priceNotice: "Los proveedores sin precios publicados siguen visibles.",
    publishedPrices: "Precios publicados para {count} procedimientos",
    publishedPricesOne: "Precios publicados para {count} procedimiento",
    priceNotAvailable: "Precio publicado no disponible actualmente en Carevero",
    cmsOverall: "Calificación general de CMS",
    viewProvider: "Ver proveedor",
    noResults: "Ningún proveedor coincide con estos filtros",
    noResultsHelp: "Pruebe otro tipo de proveedor, región o limpie los filtros.",
    prev: "Anterior",
    next: "Siguiente",
    pageOf: "Página {page} de {total}",
    filters: "Filtros",
    applyFilters: "Ver resultados",
    closeFilters: "Cerrar",
    viewSwitcherLabel: "Vista del directorio",
    paginationLabel: "Páginas del directorio de proveedores",
    filterRegionLabel: "Filtrar por región",
    mapUnavailable: "No se pudo cargar el mapa. Cambie a Lista o Cuadrícula para explorar.",
    unavailableTitle: "Proveedores",
    unavailable: "El directorio de proveedores no está disponible temporalmente.",
  },
  vi: {
    navLabel: "Nhà cung cấp",
    eyebrow: "Danh bạ nhà cung cấp",
    title: "Tìm nhà cung cấp dịch vụ y tế",
    lede: "Bệnh viện, phòng xét nghiệm, cấp cứu nhanh, trung tâm chẩn đoán hình ảnh, trung tâm phẫu thuật, vật lý trị liệu và hơn thế nữa.",
    free: "Miễn phí",
    noAccount: "Không cần tài khoản",
    verifiedData: "Dữ liệu nhà cung cấp đã xác minh",
    searchLabel: "Tìm nhà cung cấp",
    searchPlaceholder: "Tìm nhà cung cấp, thành phố hoặc mã ZIP",
    search: "Tìm",
    providerType: "Loại nhà cung cấp",
    allTypes: "Tất cả loại",
    hasPrices: "Có giá",
    hasPricesAny: "Bất kỳ",
    hasPricesYes: "Có giá đã công bố",
    hasPricesNo: "Hiện chưa có giá",
    sortBy: "Sắp xếp theo",
    sortNameAsc: "Tên (A–Z)",
    sortNameDesc: "Tên (Z–A)",
    clear: "Xóa",
    state: "Tiểu bang",
    region: "Vùng",
    allRegions: "Tất cả các vùng",
    allChip: "Tất cả",
    more: "Thêm",
    viewList: "Danh sách",
    viewGrid: "Lưới",
    viewMap: "Bản đồ",
    showing: "Hiển thị {from}–{to} trong số {total} địa điểm",
    showingTyped: "Hiển thị {from}–{to} trong số {total} địa điểm {type}",
    perPage: "{count} mỗi trang",
    priceNotice: "Các nhà cung cấp chưa có giá công bố vẫn hiển thị.",
    publishedPrices: "Giá đã công bố cho {count} thủ thuật",
    publishedPricesOne: "Giá đã công bố cho {count} thủ thuật",
    priceNotAvailable: "Giá công bố hiện chưa có trong Carevero",
    cmsOverall: "Xếp hạng tổng thể CMS",
    viewProvider: "Xem nhà cung cấp",
    noResults: "Không có nhà cung cấp nào khớp với bộ lọc",
    noResultsHelp: "Hãy thử loại nhà cung cấp khác, vùng khác, hoặc xóa bộ lọc.",
    prev: "Trước",
    next: "Sau",
    pageOf: "Trang {page} / {total}",
    filters: "Bộ lọc",
    applyFilters: "Xem kết quả",
    closeFilters: "Đóng",
    viewSwitcherLabel: "Chế độ xem danh bạ",
    paginationLabel: "Các trang danh bạ nhà cung cấp",
    filterRegionLabel: "Lọc theo vùng",
    mapUnavailable: "Không tải được bản đồ. Chuyển sang Danh sách hoặc Lưới để duyệt.",
    unavailableTitle: "Nhà cung cấp",
    unavailable: "Danh bạ nhà cung cấp tạm thời không khả dụng.",
  },
  "zh-CN": {
    navLabel: "提供者",
    eyebrow: "提供者目录",
    title: "查找医疗提供者",
    lede: "医院、化验室、紧急护理、影像中心、手术中心、物理治疗等。",
    free: "免费使用",
    noAccount: "无需账户",
    verifiedData: "已验证的提供者数据",
    searchLabel: "搜索提供者",
    searchPlaceholder: "搜索提供者、城市或邮编",
    search: "搜索",
    providerType: "提供者类型",
    allTypes: "所有类型",
    hasPrices: "有价格",
    hasPricesAny: "任意",
    hasPricesYes: "有已公布价格",
    hasPricesNo: "暂无价格",
    sortBy: "排序方式",
    sortNameAsc: "名称（A–Z）",
    sortNameDesc: "名称（Z–A）",
    clear: "清除",
    state: "州",
    region: "地区",
    allRegions: "所有地区",
    allChip: "全部",
    more: "更多",
    viewList: "列表",
    viewGrid: "网格",
    viewMap: "地图",
    showing: "显示第 {from}–{to} 个，共 {total} 个地点",
    showingTyped: "显示第 {from}–{to} 个，共 {total} 个{type}地点",
    perPage: "每页 {count} 个",
    priceNotice: "没有已公布价格的提供者仍会显示。",
    publishedPrices: "{count} 个项目的已公布价格",
    publishedPricesOne: "{count} 个项目的已公布价格",
    priceNotAvailable: "Carevero 目前暂无已公布价格",
    cmsOverall: "CMS 总体评分",
    viewProvider: "查看提供者",
    noResults: "没有提供者符合这些筛选条件",
    noResultsHelp: "请尝试其他提供者类型、地区，或清除筛选条件。",
    prev: "上一页",
    next: "下一页",
    pageOf: "第 {page} 页，共 {total} 页",
    filters: "筛选",
    applyFilters: "查看结果",
    closeFilters: "关闭",
    viewSwitcherLabel: "目录视图",
    paginationLabel: "提供者目录分页",
    filterRegionLabel: "按地区筛选",
    mapUnavailable: "无法加载地图。请切换到列表或网格浏览提供者。",
    unavailableTitle: "提供者",
    unavailable: "提供者目录暂时不可用。",
  },
  "zh-TW": {
    navLabel: "提供者",
    eyebrow: "提供者目錄",
    title: "尋找醫療提供者",
    lede: "醫院、化驗室、緊急照護、影像中心、手術中心、物理治療等。",
    free: "免費使用",
    noAccount: "無需帳戶",
    verifiedData: "已驗證的提供者資料",
    searchLabel: "搜尋提供者",
    searchPlaceholder: "搜尋提供者、城市或郵遞區號",
    search: "搜尋",
    providerType: "提供者類型",
    allTypes: "所有類型",
    hasPrices: "有價格",
    hasPricesAny: "任何",
    hasPricesYes: "有已公布價格",
    hasPricesNo: "暫無價格",
    sortBy: "排序方式",
    sortNameAsc: "名稱（A–Z）",
    sortNameDesc: "名稱（Z–A）",
    clear: "清除",
    state: "州",
    region: "地區",
    allRegions: "所有地區",
    allChip: "全部",
    more: "更多",
    viewList: "清單",
    viewGrid: "網格",
    viewMap: "地圖",
    showing: "顯示第 {from}–{to} 個，共 {total} 個地點",
    showingTyped: "顯示第 {from}–{to} 個，共 {total} 個{type}地點",
    perPage: "每頁 {count} 個",
    priceNotice: "沒有已公布價格的提供者仍會顯示。",
    publishedPrices: "{count} 個項目的已公布價格",
    publishedPricesOne: "{count} 個項目的已公布價格",
    priceNotAvailable: "Carevero 目前暫無已公布價格",
    cmsOverall: "CMS 整體評分",
    viewProvider: "檢視提供者",
    noResults: "沒有提供者符合這些篩選條件",
    noResultsHelp: "請嘗試其他提供者類型、地區，或清除篩選條件。",
    prev: "上一頁",
    next: "下一頁",
    pageOf: "第 {page} 頁，共 {total} 頁",
    filters: "篩選",
    applyFilters: "查看結果",
    closeFilters: "關閉",
    viewSwitcherLabel: "目錄檢視",
    paginationLabel: "提供者目錄分頁",
    filterRegionLabel: "依地區篩選",
    mapUnavailable: "無法載入地圖。請切換到清單或網格瀏覽提供者。",
    unavailableTitle: "提供者",
    unavailable: "提供者目錄暫時無法使用。",
  },
};
