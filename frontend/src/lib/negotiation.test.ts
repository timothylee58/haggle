import { describe, expect, it } from "vitest";
import { applyEvent, currentRound, emptyMatch, leadingSeat, meterPosition, refereeCall, resultHeadline, seatsOf, warHeadline, type Seat, type Turn } from "./negotiation";

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

describe("bidding war state", () => {
  const seat = (id: string, bid: number | null, state: Seat["state"] = "bidding"): Seat => ({ id, name: id.toUpperCase(), bid, face: 70, patience: 70, state });
  const started = applyEvent(emptyMatch, {
    type: "negotiation_started",
    data: { item: "x", currency: "MYR", opening_ask: 1288, max_rounds: 6, mode: "bidding_war", bidders: [{ id: "a", name: "A" }, { id: "b", name: "B" }] },
  });

  it("reads the mode and the bidders, and starts every seat empty", () => {
    expect(started.mode).toBe("bidding_war");
    expect(seatsOf(started).map((s) => [s.id, s.bid])).toEqual([["a", null], ["b", null]]);
  });
  it("shows the board from the latest move and the round it belongs to", () => {
    const board = [seat("a", 700), seat("b", 760)];
    const match = applyEvent(started, { type: "turn", data: { ...turn, turn: 5, round: 2, bidders: board } });
    expect(seatsOf(match)).toEqual(board);
    expect(currentRound(match)).toBe(2);
  });
  it("picks the leader among live seats only, and keeps the first on a tie", () => {
    expect(leadingSeat([seat("a", 700), seat("b", 760)])?.id).toBe("b");
    expect(leadingSeat([seat("a", 800, "thrown_out"), seat("b", 760)])?.id).toBe("b");
    expect(leadingSeat([seat("a", 760), seat("b", 760)])?.id).toBe("a");
    expect(leadingSeat([seat("a", null)])).toBeNull();
  });
  it("names the winner in the headline", () => {
    const ended = applyEvent(started, { type: "negotiation_ended", data: { status: "deal", final_price: 968, winner: { id: "b", name: "B" } } }).ended!;
    expect(warHeadline(ended, "MYR")).toBe("B wins at MYR 968");
    expect(warHeadline({ status: "buyer_walked", finalPrice: null, winner: null }, "MYR")).toBe("Every buyer walked away");
  });
  it("still reads a two-party match as before", () => {
    const match = applyEvent(emptyMatch, { type: "negotiation_started", data: { item: "x", currency: "MYR", opening_ask: 1288, max_rounds: 6 } });
    expect(match.mode).toBe("duel");
    expect(currentRound(applyEvent(match, { type: "turn", data: turn }))).toBe(1);
  });
});

