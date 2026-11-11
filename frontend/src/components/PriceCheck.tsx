"use client";

import { Loader2, Search, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { searchMarket, type MarketProduct, type MarketResult, type MarketSnapshot } from "@/lib/market";

const money = (value: number, currency: string) => `${currency} ${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;

/** Real products and prices for the item name, from Channel3. Picking one fills in sensible starting prices. */
export function PriceCheck({
  getQuery,
  onUse,
  selected,
  onClear,
}: {
  getQuery: () => string;
  onUse: (product: MarketProduct) => void;
  selected: MarketSnapshot | null;
  onClear: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MarketResult | null>(null);

  async function check() {
    const query = getQuery().trim();
    if (query.length < 2) {
      setError("Type what's being sold first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult(await searchMarket(query));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof TypeError ? "Can't reach the API. Try again." : (caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" disabled={busy} onClick={check} className="h-10 border-line-strong hover:bg-accent">
          {busy ? <Loader2 aria-hidden className="animate-spin" /> : <Search aria-hidden />} Check real prices
        </Button>
        <p className="text-sm text-muted-foreground">Starts the haggle from what it really costs. Prices from Channel3.</p>
      </div>

      {error && <p role="alert" className="text-base text-foreground">{error}</p>}

      {result && result.products.length === 0 && (
        <p className="text-muted-foreground">No products found for &ldquo;{result.query}&rdquo;. Try a more specific name, like a model number.</p>
      )}

      {result && result.products.length > 0 && (
        <div className="grid gap-2">
          {result.stats && (
            <p className="text-sm text-muted-foreground">
              New, these run {money(result.stats.low, result.stats.currency)} to {money(result.stats.high, result.stats.currency)}, typically{" "}
              {money(result.stats.median, result.stats.currency)}.
            </p>
          )}
          <ul className="grid gap-2">
            {result.products.map((product) => (
              <li key={product.id} className="grid grid-cols-[3rem_1fr_auto] items-center gap-3 border border-line bg-field p-2 pr-3">
                {product.image_url ? (
                  // Retailer images come from many hosts, so a plain image beats configuring them all.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={product.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" className="size-12 bg-background object-contain" />
                ) : (
                  <span aria-hidden className="size-12 bg-background" />
                )}
                <div className="min-w-0">
                  <p className="truncate text-base font-medium">{product.title}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {[product.brand, product.retailer].filter(Boolean).join(" · ") || "Retailer unknown"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-display text-xl font-bold tabular-nums">{money(product.price, product.currency)}</span>
                  <Button type="button" size="sm" onClick={() => onUse(product)} className="bg-referee text-referee-ink hover:bg-referee/85">
                    Use
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {selected && (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span className="bg-referee px-2 py-0.5 font-semibold text-referee-ink">Reference</span>
          <span className="text-muted-foreground">
            {money(selected.price, selected.currency)}
            {selected.retailer ? ` at ${selected.retailer}` : ""} is shown to spectators.
          </span>
          <button type="button" onClick={onClear} className="inline-flex items-center gap-1 underline underline-offset-4 outline-offset-2 hover:text-referee focus-visible:outline-2 focus-visible:outline-referee">
            <X aria-hidden className="size-3.5" /> Clear
          </button>
        </p>
      )}
    </div>
  );
}
