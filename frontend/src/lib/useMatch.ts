"use client";

import { useEffect, useRef, useState } from "react";
import { applyEvent, emptyMatch, type Match, type MatchEvent } from "./negotiation";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PACE_MS = 1400;

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

    const release = () => {
      const next = queue.current.shift();
      if (next) setMatch((current) => applyEvent(current, next));
      // The opening event carries no action, so the first turn follows straight away.
      timer = setTimeout(release, next?.type === "negotiation_started" ? 200 : PACE_MS);
    };
    let timer = setTimeout(release, 100);

    return () => {
      source.close();
      clearTimeout(timer);
    };
  }, [dealId]);

  return { match, connection };
}
