"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

const EASE = [0.16, 1, 0.3, 1] as const;
const START = 70;
const WALK_BELOW = 30;

// The same scores the referee uses in the live app.
const MOVES = [
  { label: "Fair concession", detail: "A buyer moves up a step", delta: 2 },
  { label: "Lucky number", detail: "An offer with an 8 in it", delta: 1 },
  { label: "Lowball", detail: "An offer under half the ask", delta: -20 },
  { label: "Insulting number", detail: "A price like 444", delta: -30 },
];

export function FaceDemo() {
  const reduced = useReducedMotion();
  const [face, setFace] = useState(START);
  const [lastMove, setLastMove] = useState<string | null>(null);
  const walked = face < WALK_BELOW;

  function play(label: string, delta: number) {
    setFace((current) => Math.max(0, Math.min(100, current + delta)));
    setLastMove(`${label} ${delta > 0 ? "+" : "−"}${Math.abs(delta)}`);
  }

  function reset() {
    setFace(START);
    setLastMove(null);
  }

  return (
    <div className="grid gap-6 border border-line-strong bg-card p-5 sm:p-7">
      <div>
        <div className="flex items-end justify-between gap-4">
          <p className="font-display text-xl font-bold uppercase text-seller sm:text-2xl">Seller&apos;s face</p>
          <p className="font-display text-6xl font-bold leading-none tabular-nums sm:text-7xl">{face}</p>
        </div>
        <div
          role="meter"
          aria-label="Seller's face"
          aria-valuenow={face}
          aria-valuemin={0}
          aria-valuemax={100}
          className="relative mt-3 h-3 bg-line"
        >
          <motion.div
            className={`h-full ${walked ? "bg-live" : "bg-seller"}`}
            initial={false}
            animate={{ width: `${face}%` }}
            transition={reduced ? { duration: 0 } : { duration: 0.6, ease: EASE }}
          />
          <span aria-hidden className="absolute -inset-y-1.5 w-0.5 bg-foreground" style={{ left: `${WALK_BELOW}%` }} />
        </div>
        <p className="mt-2 text-sm text-muted-foreground" style={{ marginLeft: `${WALK_BELOW}%` }}>
          <span className="-ml-1">Walks away below {WALK_BELOW}</span>
        </p>
      </div>

      <div aria-live="polite" className="min-h-14">
        <AnimatePresence mode="wait" initial={false}>
          {walked ? (
            <motion.p
              key="walked"
              initial={reduced ? false : { opacity: 0, clipPath: "inset(0 100% 0 0)" }}
              animate={{ opacity: 1, clipPath: "inset(0 0% 0 0)" }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5, ease: EASE }}
              className="bg-live px-4 py-2 font-display text-3xl font-bold uppercase leading-none text-white sm:text-4xl"
            >
              The seller walks away
            </motion.p>
          ) : (
            <motion.p key="talking" initial={false} animate={{ opacity: 1 }} className="py-2 text-muted-foreground">
              {lastMove ? `Last move: ${lastMove}.` : "Tap a move and watch the seller's face."}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      <ul className="grid gap-2">
        {MOVES.map((move) => (
          <li key={move.label}>
            <Button
              type="button"
              variant="outline"
              disabled={walked}
              onClick={() => play(move.label, move.delta)}
              className="h-auto w-full justify-between gap-4 rounded-sm border-line-strong px-4 py-3 text-left hover:bg-accent"
            >
              <span className="grid">
                <span className="text-base font-medium">{move.label}</span>
                <span className="text-sm font-normal text-muted-foreground">{move.detail}</span>
              </span>
              <span className={`font-display text-3xl font-bold tabular-nums ${move.delta > 0 ? "text-referee" : "text-seller"}`}>
                {move.delta > 0 ? "+" : "−"}{Math.abs(move.delta)}
              </span>
            </Button>
          </li>
        ))}
      </ul>

      <Button type="button" variant="ghost" onClick={reset} className="justify-self-start px-2 text-muted-foreground">
        <RotateCcw aria-hidden /> Reset
      </Button>
    </div>
  );
}
