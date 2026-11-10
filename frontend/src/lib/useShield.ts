"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "./useMatch";

export type ShieldState = "negotiated" | "authorized" | "shipped" | "delivered" | "captured" | "refunded" | "voided";

export type ShieldView = {
  state: ShieldState;
  step: string;
  amount_minor: number;
  currency: string;
  tracking_number: string | null;
  carrier: string | null;
  gateway: "simulated" | "paypal_sandbox";
  approve_url?: string | null;
};

export type ShieldLogEntry = { id: string; view: ShieldView };

const FINISHED: ShieldState[] = ["refunded", "voided"];

export function useShield(dealId: string, enabled: boolean) {
  const [view, setView] = useState<ShieldView | null>(null);
  const [log, setLog] = useState<ShieldLogEntry[]>([]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    fetch(`${API_URL}/deals/${dealId}/shield`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data: ShieldView | null) => {
        if (data && !cancelled) setView((current) => current ?? data);
      })
      .catch(() => undefined);
    const source = new EventSource(`${API_URL}/deals/${dealId}/shield/events`);
    source.addEventListener("shield", (message) => {
      const next = JSON.parse((message as MessageEvent<string>).data) as ShieldView;
      const id = (message as MessageEvent<string>).lastEventId;
      setView(next);
      setLog((current) => (current.some((entry) => entry.id === id) ? current : [...current, { id, view: next }]));
      if (FINISHED.includes(next.state)) source.close();
    });
    return () => {
      cancelled = true;
      source.close();
    };
  }, [dealId, enabled]);

  const act = useCallback(
    async (step: string, body?: object): Promise<ShieldView> => {
      const response = await fetch(`${API_URL}/deals/${dealId}/shield/${step}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Check that field and try again.");
      }
      setView(data);
      return data;
    },
    [dealId],
  );

  return { view, log, act };
}
