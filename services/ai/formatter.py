# ruff: noqa: E501
from __future__ import annotations

from decimal import Decimal

from services.ai.schemas import CareveroAIContext, Locale


def _safe_label(value: str) -> str:
    lowered = value.lower()
    if any(
        marker in lowered
        for marker in ("ignore previous", "system prompt", "developer message", "<carevero_data")
    ):
        return "[source label omitted]"
    return " ".join(value.split())[:160]


_COPY = {
    "en": {
        "intro": "Carevero found {count} nearby option(s) with published information for {procedure}.",
        "cash": "published cash price",
        "missing": "cash price not available",
        "distance": "{value} miles",
        "payer": "The hospital publishes pricing associated with {payer}. This does not confirm that your specific plan is in-network or that the service is covered.",
        "limit": "These are published prices, not personalized estimates. Your final cost may differ.",
        "empty": "We couldn't find a published price for this search. This does not necessarily mean a hospital does not offer the service.",
    },
    "es": {
        "intro": "Carevero encontró {count} opción(es) cercana(s) con información publicada para {procedure}.",
        "cash": "precio en efectivo publicado",
        "missing": "precio en efectivo no disponible",
        "distance": "{value} millas",
        "payer": "El hospital publica precios asociados con {payer}. Esto no confirma que su plan específico esté dentro de la red ni que el servicio esté cubierto.",
        "limit": "Son precios publicados, no estimaciones personalizadas. Su costo final puede variar.",
        "empty": "No encontramos un precio publicado para esta búsqueda. Esto no significa necesariamente que el hospital no ofrezca el servicio.",
    },
    "vi": {
        "intro": "Carevero tìm thấy {count} lựa chọn gần đây có thông tin được công bố cho {procedure}.",
        "cash": "giá tiền mặt được công bố",
        "missing": "không có giá tiền mặt",
        "distance": "{value} dặm",
        "payer": "Bệnh viện công bố giá liên quan đến {payer}. Điều này không xác nhận chương trình cụ thể của bạn thuộc mạng lưới hoặc dịch vụ được bảo hiểm.",
        "limit": "Đây là giá được công bố, không phải ước tính cá nhân. Chi phí cuối cùng có thể khác.",
        "empty": "Chúng tôi không tìm thấy giá được công bố cho tìm kiếm này. Điều này không nhất thiết có nghĩa là bệnh viện không cung cấp dịch vụ.",
    },
    "zh-TW": {
        "intro": "Carevero 找到 {count} 個附近選項，提供 {procedure} 的公開資訊。",
        "cash": "公開自費價格",
        "missing": "無可用自費價格",
        "distance": "{value} 英里",
        "payer": "醫院公布了與 {payer} 相關的價格。這不代表您的特定計畫屬於網內或涵蓋此服務。",
        "limit": "這些是公開價格，不是個人化估價。您的最終費用可能不同。",
        "empty": "我們找不到此搜尋的公開價格。這不一定表示醫院不提供此服務。",
    },
    "zh-CN": {
        "intro": "Carevero 找到 {count} 个附近选项，提供 {procedure} 的公开信息。",
        "cash": "公开自费价格",
        "missing": "无可用自费价格",
        "distance": "{value} 英里",
        "payer": "医院公布了与 {payer} 相关的价格。这不代表您的特定计划属于网内或涵盖此服务。",
        "limit": "这些是公开价格，不是个性化估价。您的最终费用可能不同。",
        "empty": "我们找不到此搜索的公开价格。这不一定表示医院不提供此服务。",
    },
}


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def format_grounded(context: CareveroAIContext, locale: Locale) -> str:
    copy = _COPY[locale]
    priced = [item for item in context.facilities if item.comparable_cash_price is not None]
    if not context.facilities or not any(
        item.service_availability_state == "published_price_found" for item in context.facilities
    ):
        return copy["empty"]
    lines = [copy["intro"].format(count=len(context.facilities), procedure=context.procedure_name)]
    ordered = sorted(
        context.facilities,
        key=lambda item: (item.comparable_cash_price is None, item.comparable_cash_price or 0),
    )[:5]
    for item in ordered:
        price = (
            _money(item.comparable_cash_price)
            if item.comparable_cash_price is not None
            else copy["missing"]
        )
        distance = (
            f" — {copy['distance'].format(value=item.distance_miles)}"
            if item.distance_miles is not None
            else ""
        )
        lines.append(f"{_safe_label(item.name)} — {price}{distance}")
    if context.payer_name:
        lines.append(copy["payer"].format(payer=context.payer_name))
    if priced:
        lines.append(copy["limit"])
    return "\n".join(lines)
