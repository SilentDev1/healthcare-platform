from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SUPPORTED_LOCALES = ("en", "es", "vi", "zh-TW", "zh-CN")


@dataclass(frozen=True)
class ConsumerCategory:
    slug: str
    i18n_key: str
    labels: dict[str, str]
    aliases: tuple[str, ...]

    def label(self, locale: str) -> str:
        return self.labels.get(locale, self.labels["en"])

    @property
    def searchable_terms(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.labels.values(), *self.aliases)))


@lru_cache(maxsize=1)
def consumer_categories() -> dict[str, ConsumerCategory]:
    path = Path(__file__).resolve().parents[2] / "data" / "consumer_procedure_categories.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    categories: dict[str, ConsumerCategory] = {}
    for item in payload:
        labels = item["labels"]
        if set(labels) != set(SUPPORTED_LOCALES):
            raise ValueError(f"category {item['slug']} must define every supported locale")
        category = ConsumerCategory(
            slug=item["slug"],
            i18n_key=item["i18n_key"],
            labels=labels,
            aliases=tuple(item["aliases"]),
        )
        if category.slug in categories:
            raise ValueError(f"duplicate consumer category: {category.slug}")
        categories[category.slug] = category
    return categories
