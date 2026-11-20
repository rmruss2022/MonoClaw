/**
 * Recipe toolkit — the discovery/planning half of the cooking agent.
 *
 * A local, zero-dependency catalog plus query/suggest/summarize/scale helpers.
 * The cooking-mode state machine lives in cooking.ts; HTTP wiring in index.ts;
 * voice intents in voiceagent.ts. Recipes are static seed data for now (no
 * durable store needed) but the shapes are ready for user-added recipes later.
 */

export interface Ingredient {
  item: string;
  qty?: number;        // base quantity for `servings`
  unit?: string;       // "g", "cup", "tbsp", "clove", "" …
  note?: string;       // "finely chopped"
}

export interface Step {
  n: number;
  text: string;
  durationSec?: number;   // suggested timer for this step, if any
  timerLabel?: string;    // what to call the timer ("simmer", "bake")
}

export type Diet =
  | "vegetarian" | "vegan" | "gluten-free" | "dairy-free"
  | "nut-free" | "pescatarian" | "keto";

export interface Recipe {
  id: string;
  title: string;
  cuisine: string;
  description: string;
  servings: number;            // base servings the quantities are written for
  prepMin: number;
  cookMin: number;
  difficulty: "easy" | "medium" | "hard";
  dietary: Diet[];
  tags: string[];              // breakfast/lunch/dinner/dessert/quick/comfort/one-pot…
  calories?: number;           // approx per serving
  ingredients: Ingredient[];
  steps: Step[];
}

export const totalMin = (r: Recipe): number => r.prepMin + r.cookMin;

// ---------------------------------------------------------------------------
// Seed catalog — a compact but varied set spanning the dietary tags.
// ---------------------------------------------------------------------------
const CATALOG: Recipe[] = [
  {
    id: "garlic-butter-pasta", title: "Garlic Butter Pasta", cuisine: "Italian",
    description: "A fast weeknight pasta — silky garlic butter sauce with parmesan.",
    servings: 2, prepMin: 5, cookMin: 15, difficulty: "easy",
    dietary: ["vegetarian", "nut-free"], tags: ["dinner", "quick", "comfort", "pasta"], calories: 520,
    ingredients: [
      { item: "spaghetti", qty: 200, unit: "g" },
      { item: "butter", qty: 3, unit: "tbsp" },
      { item: "garlic", qty: 4, unit: "clove", note: "thinly sliced" },
      { item: "parmesan", qty: 40, unit: "g", note: "grated" },
      { item: "parsley", qty: 2, unit: "tbsp", note: "chopped" },
      { item: "salt & pepper", note: "to taste" },
    ],
    steps: [
      { n: 1, text: "Bring a large pot of salted water to a boil.", durationSec: 480, timerLabel: "boil water" },
      { n: 2, text: "Add the spaghetti and cook until al dente.", durationSec: 600, timerLabel: "pasta" },
      { n: 3, text: "Meanwhile, melt the butter in a pan over low heat and gently cook the garlic until fragrant — don't brown it.", durationSec: 180, timerLabel: "garlic" },
      { n: 4, text: "Reserve a cup of pasta water, then drain the pasta." },
      { n: 5, text: "Toss the pasta in the garlic butter with a splash of pasta water and the parmesan until glossy." },
      { n: 6, text: "Finish with parsley, salt, and pepper. Serve hot." },
    ],
  },
  {
    id: "overnight-oats", title: "Berry Overnight Oats", cuisine: "American",
    description: "No-cook make-ahead breakfast — creamy oats with berries.",
    servings: 1, prepMin: 5, cookMin: 0, difficulty: "easy",
    dietary: ["vegetarian", "vegan", "dairy-free", "nut-free"], tags: ["breakfast", "quick", "no-cook", "make-ahead"], calories: 350,
    ingredients: [
      { item: "rolled oats", qty: 50, unit: "g" },
      { item: "oat milk", qty: 120, unit: "ml" },
      { item: "chia seeds", qty: 1, unit: "tbsp" },
      { item: "maple syrup", qty: 1, unit: "tbsp" },
      { item: "mixed berries", qty: 60, unit: "g" },
    ],
    steps: [
      { n: 1, text: "Stir the oats, milk, chia, and maple syrup together in a jar." },
      { n: 2, text: "Top with berries and seal." },
      { n: 3, text: "Refrigerate overnight (at least 4 hours). Eat cold." },
    ],
  },
  {
    id: "chickpea-curry", title: "Coconut Chickpea Curry", cuisine: "Indian",
    description: "A cozy, fragrant one-pot curry that's naturally vegan.",
    servings: 4, prepMin: 10, cookMin: 25, difficulty: "easy",
    dietary: ["vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free"], tags: ["dinner", "one-pot", "comfort", "curry"], calories: 430,
    ingredients: [
      { item: "chickpeas", qty: 2, unit: "can", note: "drained" },
      { item: "coconut milk", qty: 1, unit: "can" },
      { item: "onion", qty: 1, note: "diced" },
      { item: "garlic", qty: 3, unit: "clove", note: "minced" },
      { item: "ginger", qty: 1, unit: "tbsp", note: "grated" },
      { item: "curry powder", qty: 2, unit: "tbsp" },
      { item: "diced tomatoes", qty: 1, unit: "can" },
      { item: "spinach", qty: 100, unit: "g" },
    ],
    steps: [
      { n: 1, text: "Sauté the onion in oil until soft, then add garlic and ginger for a minute.", durationSec: 300, timerLabel: "soften onion" },
      { n: 2, text: "Stir in the curry powder and cook until fragrant." },
      { n: 3, text: "Add tomatoes, chickpeas, and coconut milk. Simmer to thicken.", durationSec: 900, timerLabel: "simmer" },
      { n: 4, text: "Stir in the spinach until wilted. Season and serve over rice." },
    ],
  },
  {
    id: "sheet-pan-salmon", title: "Sheet-Pan Salmon & Veg", cuisine: "American",
    description: "Hands-off roasted salmon with vegetables on one tray.",
    servings: 2, prepMin: 10, cookMin: 18, difficulty: "easy",
    dietary: ["pescatarian", "gluten-free", "dairy-free", "nut-free", "keto"], tags: ["dinner", "sheet-pan", "healthy", "quick"], calories: 480,
    ingredients: [
      { item: "salmon fillets", qty: 2 },
      { item: "broccoli", qty: 200, unit: "g", note: "florets" },
      { item: "cherry tomatoes", qty: 150, unit: "g" },
      { item: "olive oil", qty: 2, unit: "tbsp" },
      { item: "lemon", qty: 1 },
      { item: "salt & pepper", note: "to taste" },
    ],
    steps: [
      { n: 1, text: "Heat the oven to 220°C / 425°F.", durationSec: 600, timerLabel: "preheat" },
      { n: 2, text: "Toss the broccoli and tomatoes with oil, salt, and pepper on a sheet pan." },
      { n: 3, text: "Nestle the salmon in, squeeze over half the lemon." },
      { n: 4, text: "Roast until the salmon flakes easily.", durationSec: 900, timerLabel: "roast" },
      { n: 5, text: "Finish with the remaining lemon and serve." },
    ],
  },
  {
    id: "margherita-flatbread", title: "Margherita Flatbread", cuisine: "Italian",
    description: "Crisp flatbread with tomato, mozzarella, and basil.",
    servings: 2, prepMin: 10, cookMin: 12, difficulty: "easy",
    dietary: ["vegetarian", "nut-free"], tags: ["dinner", "lunch", "quick", "pizza"], calories: 560,
    ingredients: [
      { item: "flatbread or naan", qty: 2 },
      { item: "passata", qty: 120, unit: "ml" },
      { item: "fresh mozzarella", qty: 125, unit: "g", note: "torn" },
      { item: "basil", qty: 8, unit: "leaf" },
      { item: "olive oil", qty: 1, unit: "tbsp" },
    ],
    steps: [
      { n: 1, text: "Heat the oven to 230°C / 450°F.", durationSec: 600, timerLabel: "preheat" },
      { n: 2, text: "Spread passata over the flatbreads and dot with mozzarella." },
      { n: 3, text: "Bake until bubbling and the edges are crisp.", durationSec: 720, timerLabel: "bake" },
      { n: 4, text: "Top with basil and a drizzle of olive oil. Slice and serve." },
    ],
  },
  {
    id: "veggie-stir-fry", title: "15-Minute Veggie Stir-Fry", cuisine: "Chinese",
    description: "Crunchy vegetables in a quick soy-ginger sauce.",
    servings: 2, prepMin: 10, cookMin: 8, difficulty: "easy",
    dietary: ["vegetarian", "vegan", "dairy-free", "nut-free"], tags: ["dinner", "quick", "healthy", "one-pot"], calories: 310,
    ingredients: [
      { item: "mixed vegetables", qty: 400, unit: "g", note: "sliced" },
      { item: "garlic", qty: 2, unit: "clove", note: "minced" },
      { item: "ginger", qty: 1, unit: "tbsp", note: "grated" },
      { item: "soy sauce", qty: 3, unit: "tbsp", note: "use tamari for gluten-free" },
      { item: "sesame oil", qty: 1, unit: "tbsp" },
      { item: "cooked rice", qty: 2, unit: "cup", note: "to serve" },
    ],
    steps: [
      { n: 1, text: "Get the wok or pan very hot with a little oil." },
      { n: 2, text: "Stir-fry the hardest vegetables first, then the rest, keeping them moving.", durationSec: 300, timerLabel: "stir-fry" },
      { n: 3, text: "Add garlic, ginger, soy, and sesame oil; toss for one more minute." },
      { n: 4, text: "Serve over rice." },
    ],
  },
  {
    id: "steak-eggs", title: "Keto Steak & Eggs", cuisine: "American",
    description: "A protein-packed low-carb plate — seared steak and eggs.",
    servings: 1, prepMin: 5, cookMin: 12, difficulty: "medium",
    dietary: ["gluten-free", "dairy-free", "nut-free", "keto"], tags: ["breakfast", "high-protein", "quick"], calories: 640,
    ingredients: [
      { item: "sirloin steak", qty: 1 },
      { item: "eggs", qty: 2 },
      { item: "butter or oil", qty: 1, unit: "tbsp" },
      { item: "salt & pepper", note: "to taste" },
    ],
    steps: [
      { n: 1, text: "Pat the steak dry and season well. Let it come toward room temp." },
      { n: 2, text: "Sear in a hot pan to your liking, then rest it.", durationSec: 480, timerLabel: "sear & rest" },
      { n: 3, text: "Fry the eggs in the same pan." },
      { n: 4, text: "Slice the steak and plate with the eggs." },
    ],
  },
  {
    id: "banana-pancakes", title: "Fluffy Banana Pancakes", cuisine: "American",
    description: "Weekend pancakes naturally sweetened with banana.",
    servings: 3, prepMin: 10, cookMin: 15, difficulty: "easy",
    dietary: ["vegetarian", "nut-free"], tags: ["breakfast", "dessert", "comfort", "kids"], calories: 400,
    ingredients: [
      { item: "flour", qty: 200, unit: "g" },
      { item: "banana", qty: 2, note: "mashed" },
      { item: "milk", qty: 250, unit: "ml" },
      { item: "egg", qty: 1 },
      { item: "baking powder", qty: 2, unit: "tsp" },
      { item: "butter", qty: 1, unit: "tbsp", note: "for the pan" },
    ],
    steps: [
      { n: 1, text: "Whisk the dry ingredients in one bowl, the wet in another." },
      { n: 2, text: "Fold together until just combined — a few lumps are fine." },
      { n: 3, text: "Cook ladlefuls on a buttered griddle until bubbles form, then flip.", durationSec: 180, timerLabel: "per batch" },
      { n: 4, text: "Keep warm and serve with your favorite toppings." },
    ],
  },
];

// ---------------------------------------------------------------------------
// Toolkit API
// ---------------------------------------------------------------------------

export function listRecipes(): Recipe[] { return CATALOG.slice(); }

export function getRecipe(idOrTitle: string): Recipe | undefined {
  const q = idOrTitle.trim().toLowerCase();
  if (!q) return undefined;
  return CATALOG.find((r) => r.id === q)
    || CATALOG.find((r) => r.title.toLowerCase() === q)
    || CATALOG.find((r) => r.title.toLowerCase().includes(q))
    || CATALOG.find((r) => r.id.includes(q.replace(/\s+/g, "-")));
}

/** Scale a recipe's ingredient quantities to a target serving count. */
export function scaleIngredients(r: Recipe, servings: number): Ingredient[] {
  const factor = servings > 0 ? servings / r.servings : 1;
  const round = (n: number) => Math.round(n * 100) / 100;
  return r.ingredients.map((ing) => (ing.qty == null ? ing : { ...ing, qty: round(ing.qty * factor) }));
}

export interface SuggestOpts {
  people?: number;
  diet?: string[];        // dietary tags that must ALL be satisfied
  maxMinutes?: number;
  query?: string;
  limit?: number;
}

/** Free-text + constraint filtering, ranked by relevance. */
export function suggest(opts: SuggestOpts = {}): Recipe[] {
  const diet = (opts.diet ?? []).map((d) => d.trim().toLowerCase()).filter(Boolean);
  const q = (opts.query ?? "").trim().toLowerCase();
  const limit = opts.limit ?? 6;

  let out = CATALOG.filter((r) => {
    if (diet.length && !diet.every((d) => r.dietary.includes(d as Diet))) return false;
    if (opts.maxMinutes != null && totalMin(r) > opts.maxMinutes) return false;
    return true;
  });

  if (q) {
    const scored = out
      .map((r) => ({ r, score: relevance(r, q) }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score);
    out = scored.map((x) => x.r);
  } else {
    out = out.sort((a, b) => totalMin(a) - totalMin(b)); // quickest first
  }
  return out.slice(0, limit);
}

export const search = (query: string, limit = 6): Recipe[] => suggest({ query, limit });

function relevance(r: Recipe, q: string): number {
  const hay = [r.title, r.cuisine, ...r.tags, ...r.dietary, ...r.ingredients.map((i) => i.item)]
    .join(" ").toLowerCase();
  let score = 0;
  for (const term of q.split(/\s+/).filter(Boolean)) {
    if (r.title.toLowerCase().includes(term)) score += 5;
    else if (hay.includes(term)) score += 2;
  }
  return score;
}

/** A compact object good for list views and voice. */
export function summary(r: Recipe, servings?: number) {
  const s = servings && servings > 0 ? servings : r.servings;
  return {
    id: r.id, title: r.title, cuisine: r.cuisine, description: r.description,
    servings: s, prepMin: r.prepMin, cookMin: r.cookMin, totalMin: totalMin(r),
    difficulty: r.difficulty, dietary: r.dietary, tags: r.tags, calories: r.calories,
    ingredientCount: r.ingredients.length, stepCount: r.steps.length,
  };
}

/** One-line, spoken-friendly description. */
export function sayLine(r: Recipe): string {
  return `${r.title}: ${r.difficulty}, about ${totalMin(r)} minutes, ${r.ingredients.length} ingredients, serves ${r.servings}.`;
}

/** Full detail for an app/voice read-out, ingredients scaled to servings. */
export function detail(r: Recipe, servings?: number) {
  return { ...summary(r, servings), ingredients: scaleIngredients(r, servings ?? r.servings), steps: r.steps };
}
