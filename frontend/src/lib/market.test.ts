import { describe, expect, it } from "vitest";
import { shortTitle, suggestPrices, toSnapshot } from "./market";

describe("price check helpers", () => {
  it("starts the seller at retail and keeps every buyer's budget below it", () => {
    const { ask, floor, caps } = suggestPrices(250);
    expect(ask).toBe(250);
    expect(floor).toBe(175);
    expect(caps).toEqual([213, 200, 225, 190]);
    expect(floor).toBeLessThan(ask);
    expect(Math.max(...caps)).toBeLessThanOrEqual(ask);
  });
  it("never suggests a price below one", () => {
    expect(suggestPrices(0.2)).toEqual({ ask: 1, floor: 1, caps: [1, 1, 1, 1] });
  });
  it("shortens long retailer titles at a word", () => {
    expect(shortTitle("Yamaha FG800")).toBe("Yamaha FG800");
    const long = shortTitle("Yamaha FG800 Solid Top Acoustic Guitar Natural Satin Finish with Gig Bag and Strap");
    expect(long.length).toBeLessThanOrEqual(60);
    expect(long.endsWith(" ")).toBe(false);
    expect(long.startsWith("Yamaha FG800 Solid Top")).toBe(true);
  });
  it("keeps only what spectators may see of a product", () => {
    const product = { id: "1", title: "T", brand: "B", image_url: "i", price: 9.5, currency: "USD", retailer: "r", url: "u", condition: "new" };
    expect(toSnapshot(product)).toEqual({ title: "T", price: 9.5, currency: "USD", retailer: "r", url: "u" });
  });
});
