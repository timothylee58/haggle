"use client";

import { useEffect, useRef, useState } from "react";
import { applyEvent, emptyMatch, type Match, type MatchEvent } from "./negotiation";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PACE_MS = 1400;
const WAR_PACE_MS = 1000; // a bidding war has about three times the moves
const WATCHED_KEY = "haggle:watched:";

// Remembers matches this browser has watched to the end, so coming back (for example from
// PayPal) shows the result at once instead of replaying it. Storage can be blocked.
function wasWatched(dealId: string): boolean {
  try {
    return localStorage.getItem(WATCHED_KEY + dealId) === "1";
  } catch {
    return false;
  }
}

function markWatched(dealId: string): void {
  try {
    localStorage.setItem(WATCHED_KEY + dealId, "1");
  } catch {
    // Without storage the next visit simply replays the match.
  }
}

export type Connection = "connecting" | "live" | "reconnecting" | "missing";

/** Follows the SSE stream and releases turns at a watchable pace, however fast they arrive. */
export function useMatch(dealId: string): { match: Match; connection: Connection } {
  const [match, setMatch] = useState<Match>(emptyMatch);
  const [connection, setConnection] = useState<Connection>("connecting");
  const queue = useRef<MatchEvent[]>([]);

  useEffect(() => {
    const source = new EventSource(`${API_URL}/negotiations/${dealId}/events`);
    let opened = false;
    const enqueue = (type: MatchEvent["type"]) => (message: MessageEvent<string>) => {
      queue.current.push({ type, data: JSON.parse(message.data) } as MatchEvent);
      if (type === "negotiation_ended") source.close();
    };
    source.addEventListener("negotiation_started", enqueue("negotiation_started"));
    source.addEventListener("turn", enqueue("turn"));
    source.addEventListener("negotiation_ended", enqueue("negotiation_ended"));
    source.onopen = () => {
      opened = true;
      setConnection("live");
    };
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        if (!opened) setConnection("missing");
      } else {
        setConnection("reconnecting");
      }
    };

    const instant = wasWatched(dealId);
    const release = () => {
      const batch = instant ? queue.current.splice(0) : queue.current.splice(0, 1);
      if (batch.length > 0) {
        setMatch((current) => batch.reduce((state, event) => applyEvent(state, event), current));
        if (batch.some((event) => event.type === "negotiation_ended")) markWatched(dealId);
      }
      // The opening event carries no action, so the first turn follows straight away.
      const isWarTurn = batch[0]?.type === "turn" && Boolean(batch[0].data.bidders);
      const wait = instant ? 100 : batch[0]?.type === "negotiation_started" ? 200 : isWarTurn ? WAR_PACE_MS : PACE_MS;
      timer = setTimeout(release, wait);
    };
    let timer = setTimeout(release, 100);

    return () => {
      source.close();
      clearTimeout(timer);
    };
  }, [dealId]);

  return { match, connection };
}
