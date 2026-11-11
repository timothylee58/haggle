import type { MarketSnapshot } from "./market";

export type Side = "buyer" | "seller";
export type Action = "offer" | "accept" | "walk";

export type SeatState = "bidding" | "walked" | "thrown_out" | "won";
export type BidderRef = { id: string; name: string };
/** One buyer on the board of a bidding war. Never carries a budget. */
export type Seat = BidderRef & { bid: number | null; face: number; patience: number; state: SeatState };

export type Turn = {
  turn: number;
  side: Side;
  action: Action;
  price: number | null;
  requested_price: number | null;
  overridden: boolean;
  message: string;
  last_bid: number | null;
  last_ask: number | null;
  gap: number | null;
  buyer_face: number;
  seller_face: number;
  status: string;
  final_price: number | null;
  // Bidding war only.
  round?: number;
  bidder?: string;
  bidder_name?: string;
  bidders?: Seat[];
  note?: string | null;
  winner?: string | null;
};

export type Match = {
  market: MarketSnapshot | null;
  mode: "duel" | "bidding_war";
  bidders: BidderRef[];
  item: string;
  currency: string;
  openingAsk: number | null;
  maxRounds: number;
  turns: Turn[];
  firstBid: number | null;
  ended: { status: string; finalPrice: number | null; winner: BidderRef | null } | null;
};

export const emptyMatch: Match = {
  market: null,
  mode: "duel",
  bidders: [],
  item: "",
  currency: "MYR",
  openingAsk: null,
  maxRounds: 0,
  turns: [],
  firstBid: null,
  ended: null,
};

export type MatchEvent =
  | {
      type: "negotiation_started";
      data: { item: string; currency: string; opening_ask: number; max_rounds: number; mode?: string; bidders?: BidderRef[]; market?: MarketSnapshot };
    }
  | { type: "turn"; data: Turn }
  | { type: "negotiation_ended"; data: { status: string; final_price: number | null; winner?: BidderRef | null } };

export function applyEvent(match: Match, event: MatchEvent): Match {
  switch (event.type) {
    case "negotiation_started":
      return {
        ...match,
        item: event.data.item,
        currency: event.data.currency,
        openingAsk: event.data.opening_ask,
        maxRounds: event.data.max_rounds,
        mode: event.data.mode === "bidding_war" ? "bidding_war" : "duel",
        bidders: event.data.bidders ?? [],
        market: event.data.market ?? null,
      };
    case "turn":
      if (match.turns.some((t) => t.turn === event.data.turn)) return match;
      return {
        ...match,
        turns: [...match.turns, event.data],
        firstBid: match.firstBid ?? event.data.last_bid,
      };
    case "negotiation_ended":
      return { ...match, ended: { status: event.data.status, finalPrice: event.data.final_price, winner: event.data.winner ?? null } };
  }
}

export function currentRound(match: Match): number {
  const last = match.turns.at(-1);
  if (last?.round) return Math.min(match.maxRounds || last.round, last.round);
  return Math.max(1, Math.min(match.maxRounds || 1, Math.ceil(match.turns.length / 2) || 1));
}

/** Position on the meter, 0 to 100, between the first bid and the opening ask. */
export function meterPosition(value: number, low: number, high: number): number {
  if (high <= low) return 50;
  return Math.max(0, Math.min(100, ((value - low) / (high - low)) * 100));
}

export type RefereeCall = { kind: "overruled" | "snapped"; text: string };

/** Snapping moves a price about 2%. Anything larger means the rules overruled the agent. */
const SNAP_LIMIT = 0.03;

/** The referee's call, when code changed what the agent tried to do. */
export function refereeCall(turn: Turn, currency: string): RefereeCall | null {
  if (!turn.overridden) return null;
  const asked = turn.requested_price;
  if (asked !== null && turn.price !== null && asked !== turn.price) {
    const shown = (n: number) => `${currency} ${n.toLocaleString("en-US")}`;
    if (Math.abs(asked - turn.price) <= asked * SNAP_LIMIT) {
      return { kind: "snapped", text: `Lucky number: ${shown(asked)} became ${shown(turn.price)}` };
    }
    return { kind: "overruled", text: `Agent tried ${shown(asked)}. Ruled ${shown(turn.price)}.` };
  }
  if (turn.action === "accept") return { kind: "overruled", text: "Final offer. The rules decide this one." };
  if (turn.action === "walk") return { kind: "overruled", text: "Final offer is below the limit. No deal." };
  return { kind: "overruled", text: "Move changed by the rules." };
}

export function resultHeadline(status: string, currency: string, finalPrice: number | null): string {
  switch (status) {
    case "deal":
      return `Deal at ${currency} ${(finalPrice ?? 0).toLocaleString("en-US")}`;
    case "seller_walked":
      return "Seller walks away";
    case "buyer_walked":
      return "Buyer walks away";
    case "no_deal":
      return "No deal";
    default:
      return "Match abandoned";
  }
}

/** The buyers as they stand after the latest move. Before the first bid, every seat is empty. */
export function seatsOf(match: Match): Seat[] {
  const board = match.turns.at(-1)?.bidders;
  if (board) return board;
  return match.bidders.map((b) => ({ ...b, bid: null, face: 70, patience: 70, state: "bidding" as const }));
}

/** The best live bid. A tie goes to the seat listed first, as the earlier bidder usually is. */
export function leadingSeat(seats: Seat[]): Seat | null {
  let best: Seat | null = null;
  for (const seat of seats) {
    if (seat.bid === null || (seat.state !== "bidding" && seat.state !== "won")) continue;
    if (best === null || seat.bid > (best.bid ?? 0)) best = seat;
  }
  return best;
}

export function seatIndex(match: Match, id: string | undefined): number {
  const index = match.bidders.findIndex((b) => b.id === id);
  return index < 0 ? 0 : index;
}

export function warHeadline(ended: NonNullable<Match["ended"]>, currency: string): string {
  if (ended.status === "deal" && ended.winner) {
    return `${ended.winner.name} wins at ${currency} ${(ended.finalPrice ?? 0).toLocaleString("en-US")}`;
  }
  if (ended.status === "buyer_walked") return "Every buyer walked away";
  return resultHeadline(ended.status, currency, ended.finalPrice);
}

/** How the match relates to the real-world price, when the person picked one. */
export function marketLine(match: Match): string | null {
  const market = match.market;
  if (!market) return null;
  const shown = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  const where = market.retailer ? ` at ${market.retailer}` : "";
  let line = `Retail ${market.currency} ${shown(market.price)}${where}`;
  const price = match.ended?.status === "deal" ? match.ended.finalPrice : null;
  if (price !== null && match.currency === market.currency && market.price > 0) {
    const percent = Math.round((Math.abs(market.price - price) / market.price) * 100);
    if (percent > 0) line += `, deal is ${percent}% ${price < market.price ? "below" : "above"} retail`;
  }
  return line;
}
