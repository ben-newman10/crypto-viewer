/**
 * Reader-facing names for the backend's signal categories.
 *
 * The API serves these as machine values (`sentiment`, `market_structure`)
 * because that is what they are — keys the confidence rubric is expressed in.
 * Turning them into prose is a display concern, so it lives here beside the
 * other display tables in this folder (see `ACTION_TOKENS` in `badges.tsx`),
 * and the payload keeps its stable values.
 *
 * Kept in step with `CATEGORY_LABELS` in `server_py/app/schemas/grounding.py`,
 * which does the same job for the strings the backend itself writes.
 */

const CATEGORY_LABELS: Record<string, string> = {
  trend: 'price trend',
  momentum: 'momentum',
  volatility: 'price swings',
  sentiment: 'market mood',
  market_structure: 'market size',
  position: 'your holding',
  reference: 'reference data',
}

/** Plain name for a category, falling back to the raw value de-underscored. */
export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category.replace(/_/g, ' ')
}

/** Plain names for a list of categories, in the order given. */
export function categoryLabels(categories: string[]): string[] {
  return categories.map(categoryLabel)
}
