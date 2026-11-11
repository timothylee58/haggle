import { API_URL } from "./useMatch";

export type Features = { claude: boolean; market_price: boolean; payments: string };
export type MarketProduct = {
  id: string;
  title: string;
  brand: string | null;
  image_url: string | null;
  price: number;
  currency: string;
  retailer: string | null;
  url: string | null;
  condition: string | null;
};
export type MarketStats = { currency: string; low: number; median: number; high: number };
export type MarketResult = { query: string; products: MarketProduct[]; stats: MarketStats | null };
/** A reference price the person picked. It is shown to spectators and never used to decide a price. */
export type MarketSnapshot = { title: string; price: number; currency: string; retailer: string | null; url: string | null };

/** What this server can do, so the form only offers what will work. Null when the API is unreachable. */
export async function fetchFeatures(): Promise<Features | null> {
  try {
    const response = await fetch(`${API_URL}/features`);
    return response.ok ? ((await response.json()) as Features) : null;
  } catch {
    return null;
  }
}

export async function searchMarket(query: string): Promise<MarketResult> {
  const response = await fetch(`${API_URL}/market/search?q=${encodeURIComponent(query.trim())}`);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : "The price check could not run. Try again.");
  }
  return body as MarketResult;
}

export function toSnapshot(product: MarketProduct): MarketSnapshot {
  return { title: product.title, price: product.price, currency: product.currency, retailer: product.retailer, url: product.url };
}

/** A short name for the form, from a long retailer title. */
export function shortTitle(title: string, max = 60): string {
  if (title.length <= max) return title;
  const cut = title.slice(0, max);
  return cut.slice(0, Math.max(cut.lastIndexOf(" "), 20)).trimEnd();
}

/**
 * Starting prices for a haggle over something that sells for `price` new. The seller opens at the retail
 * price and will not go below 70% of it, and the buyers' budgets sit at 76 to 90%. These are editable
 * starting points for a second-hand sale, not claims about the item's value.
 */
export function suggestPrices(price: number): { ask: number; floor: number; caps: number[] } {
  const whole = (value: number) => Math.max(1, Math.round(value));
  return { ask: whole(price), floor: whole(price * 0.7), caps: [0.85, 0.8, 0.9, 0.76].map((factor) => whole(price * factor)) };
}
