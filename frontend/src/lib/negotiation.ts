export type Side = "buyer" | "seller";
export type Action = "offer" | "accept" | "walk";

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
};

export type Match = {
  item: string;
  currency: string;
  openingAsk: number | null;
  maxRounds: number;
  turns: Turn[];
  firstBid: number | null;
  ended: { status: string; finalPrice: number | null } | null;
};

export const emptyMatch: Match = {
  item: "",
  currency: "MYR",
  openingAsk: null,
  maxRounds: 0,
  turns: [],
  firstBid: null,
  ended: null,
};

export type MatchEvent =
  | { type: "negotiation_started"; data: { item: string; currency: string; opening_ask: number; max_rounds: number } }
  | { type: "turn"; data: Turn }
  | { type: "negotiation_ended"; data: { status: string; final_price: number | null } };

export function applyEvent(match: Match, event: MatchEvent): Match {
  switch (event.type) {
    case "negotiation_started":
      return {
        ...match,
        item: event.data.item,
        currency: event.data.currency,
        openingAsk: event.data.opening_ask,
        maxRounds: event.data.max_rounds,
      };
    case "turn":
      if (match.turns.some((t) => t.turn === event.data.turn)) return match;
      return {
        ...match,
        turns: [...match.turns, event.data],
        firstBid: match.firstBid ?? event.data.last_bid,
      };
    case "negotiation_ended":
      return { ...match, ended: { status: event.data.status, finalPrice: event.data.final_price } };
  }
}

export function currentRound(match: Match): number {
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
