import categoryRegistry from "../../../data/consumer_procedure_categories.json";
import type { Messages } from "./i18n";

type CategoryDefinition = {
  slug: string;
  i18n_key: keyof Messages;
};

const categories = categoryRegistry as CategoryDefinition[];

export const consumerCategoryRegistry = new Map(
  categories.map((category) => [category.slug, category]),
);

export function consumerCategoryName(
  messages: Messages,
  categorySlug: string,
): string {
  const category =
    consumerCategoryRegistry.get(categorySlug) ??
    consumerCategoryRegistry.get(categorySlug.replaceAll("_", "-"));
  if (category) return messages[category.i18n_key] as string;
  return categorySlug
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
