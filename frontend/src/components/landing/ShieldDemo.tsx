"use client";

import { AnimatePresence, motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { headline, Tracker } from "@/components/ShieldPanel";
import type { ShieldState } from "@/lib/useShield";

const EASE = [0.16, 1, 0.3, 1] as const;

const STATES: ShieldState[] = ["negotiated", "authorized", "shipped", "delivered", "captured"];

// The same lines the live Shield panel writes into its money trail.
const TRAIL = [
  "Buyer approved the hold",
  "Funds held. Seller not paid yet",
  "Seller shipped with tracking",
  "Delivery confirmed",
  "Funds released to the seller",
];

export function ShieldDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.4 });
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(1);

  useEffect(() => {
    if (reduced || !inView) return;
    // Steps land every 1.8s. Once the seller is paid, the demo holds and then starts over.
    const delay = index >= STATES.length - 1 ? 4200 : 1800;
    const timer = setTimeout(() => setIndex((current) => (current >= STATES.length - 1 ? 0 : current + 1)), delay);
    return () => clearTimeout(timer);
  }, [index, inView, reduced]);

  const shown = reduced ? 1 : index;
  const state = STATES[shown];
  const view = {
    state,
    step: "",
    amount_minor: 76800,
    currency: "MYR",
    tracking_number: shown >= 2 ? "SAMPLE123MY" : null,
    carrier: null,
    gateway: "simulated" as const,
  };

  return (
    <div ref={ref} className="grid gap-7 border border-line-strong bg-card p-5 sm:p-7">
      <div role="img" aria-label="Sample Shield: MYR 768 is held, then shipped, then delivered, then paid to the seller.">
        <div aria-hidden>
          <div className="flex flex-wrap items-center gap-3">
            <p className="font-display text-2xl font-bold uppercase">Kena Scam Shield</p>
            <span className="rounded-sm border border-line-strong px-2 py-0.5 text-sm text-muted-foreground">Sample</span>
          </div>
          <div className="mt-2 min-h-14 sm:min-h-8">
            <AnimatePresence mode="wait" initial={false}>
              <motion.p
                key={state}
                initial={reduced ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, y: -8 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="text-xl text-balance"
              >
                {headline(view)}
              </motion.p>
            </AnimatePresence>
          </div>
          <div className="mt-7">
            <Tracker state={state} shipped={Boolean(view.tracking_number)} />
          </div>
        </div>
      </div>

      <div aria-hidden>
        <p className="font-display text-xl font-bold uppercase">Money trail</p>
        <ul className="mt-3 min-h-[9.5rem] border-l border-line-strong pl-4">
          <AnimatePresence initial={false}>
            {TRAIL.slice(0, shown + 1).map((entry, entryIndex) => (
              <motion.li
                key={entry}
                initial={reduced ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.35, ease: EASE }}
                className={`py-1 ${entryIndex === shown ? "text-foreground" : "text-muted-foreground"}`}
              >
                {entry}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </div>
  );
}
