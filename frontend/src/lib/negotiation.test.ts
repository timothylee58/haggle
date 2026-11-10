import { describe, expect, it } from "vitest";
import { applyEvent, emptyMatch, meterPosition, refereeCall, resultHeadline, type Turn } from "./negotiation";

const turn: Turn = {
  turn: 1, side: "buyer", action: "offer", price: 950, requested_price: 100000, overridden: true,
  message: "hi", last_bid: 950, last_ask: 1288, gap: 338, buyer_face: 70, seller_face: 70,
  status: "ongoing", final_price: null,
};

describe("match state", () => {
  it("records the first bid once and ignores replayed turns", () => {
    let match = applyEvent(emptyMatch, { type: "turn", data: turn });
    match = applyEvent(match, { type: "turn", data: turn });
    match = applyEvent(match, { type: "turn", data: { ...turn, turn: 3, last_bid: 960 } });
    expect(match.turns).toHaveLength(2);
    expect(match.firstBid).toBe(950);
  });
  it("clamps the meter and survives an empty range", () => {
    expect(meterPosition(5, 0, 10)).toBe(50);
    expect(meterPosition(50, 0, 10)).toBe(100);
    expect(meterPosition(5, 5, 5)).toBe(50);
  });
  it("names what the referee changed", () => {
    expect(refereeCall(turn, "MYR")).toEqual({ kind: "overruled", text: "Agent tried MYR 100,000. Ruled MYR 950." });
    expect(refereeCall({ ...turn, requested_price: 955, price: 938 }, "MYR")?.kind).toBe("snapped");
    expect(refereeCall({ ...turn, overridden: false }, "MYR")).toBeNull();
  });
  it("describes results", () => {
    expect(resultHeadline("deal", "MYR", 938)).toBe("Deal at MYR 938");
    expect(resultHeadline("failed", "MYR", null)).toBe("Match abandoned");
  });
});
