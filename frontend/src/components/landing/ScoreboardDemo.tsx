"use client";

import { AnimatePresence, motion, useInView, useReducedMotion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { RollingNumber } from "@/components/RollingNumber";
import { Badge } from "@/components/ui/badge";

const EASE = [0.16, 1, 0.3, 1] as const;
const OPENING_ASK = 1288;
const FIRST_BID = 668;
const ROUNDS = 6;

type Side = "buyer" | "seller";
type Turn = {
  side: Side;
  accept?: boolean;
  price: number;
  bid: number;
  ask: number;
  buyerFace: number;
  sellerFace: number;
  note?: string;
};

// The prices come from a real run of the rule-based agents on the default match. Face scores are
// rounded for the demo. The referee notes are the real snaps from that run.
const TURNS: Turn[] = [
  { side: "buyer", price: 668, bid: 668, ask: OPENING_ASK, buyerFace: 70, sellerFace: 71 },
  { side: "seller", price: 1008, bid: 668, ask: 1008, buyerFace: 73, sellerFace: 71 },
  { side: "buyer", price: 718, bid: 718, ask: 1008, buyerFace: 73, sellerFace: 74, note: "Lucky number: MYR 719 became MYR 718" },
  { side: "seller", price: 888, bid: 718, ask: 888, buyerFace: 76, sellerFace: 74, note: "Lucky number: MYR 878 became MYR 888" },
  { side: "buyer", price: 738, bid: 738, ask: 888, buyerFace: 76, sellerFace: 77, note: "Lucky number: MYR 743 became MYR 738" },
  { side: "seller", price: 818, bid: 738, ask: 818, buyerFace: 79, sellerFace: 77, note: "Lucky number: MYR 821 became MYR 818" },
  { side: "buyer", price: 758, bid: 758, ask: 818, buyerFace: 79, sellerFace: 80 },
  { side: "seller", price: 788, bid: 758, ask: 788, buyerFace: 82, sellerFace: 80 },
  { side: "buyer", price: 768, bid: 768, ask: 788, buyerFace: 82, sellerFace: 83 },
  { side: "seller", accept: true, price: 768, bid: 768, ask: 788, buyerFace: 82, sellerFace: 83 },
];

const money = (value: number) => value.toLocaleString("en-US");
const sideText: Record<Side, string> = { buyer: "text-buyer", seller: "text-seller" };
const sideBar: Record<Side, string> = { buyer: "bg-buyer", seller: "bg-seller" };
const line = (turn: Turn) => (turn.accept ? `Okay lah, MYR ${money(turn.price)}. Deal.` : `MYR ${money(turn.price)}, how about that?`);
const position = (value: number) => Math.min(100, Math.max(0, ((value - FIRST_BID) / (OPENING_ASK - FIRST_BID)) * 100));

function Team({ side, price, face, label }: { side: Side; price: number; face: number; label: string }) {
  return (
    <div className={side === "seller" ? "text-right" : ""}>
      <p className={`font-display text-xl font-bold uppercase sm:text-2xl ${sideText[side]}`}>{side}</p>
      <p className="font-display text-5xl font-bold leading-none tabular-nums sm:text-7xl lg:text-8xl">
        <RollingNumber value={price} />
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{label}</p>
      <div className="mt-3 flex justify-between text-sm text-muted-foreground">
        <span>Face</span>
        <span className="tabular-nums text-foreground">{face}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden bg-line">
        <motion.div className={`h-full ${sideBar[side]}`} initial={false} animate={{ width: `${face}%` }} transition={{ duration: 0.6, ease: EASE }} />
      </div>
    </div>
  );
}

export function ScoreboardDemo() {
  const ref = useRef<HTMLElement>(null);
  // It sits right under the hero headline, so it starts as soon as any real part of it shows.
  const inView = useInView(ref, { amount: 0.1 });
  const reduced = useReducedMotion();
  const [count, setCount] = useState(1);

  useEffect(() => {
    if (reduced || !inView) return;
    // Each turn lands every 1.5s. At full time the result holds for a while, then the match restarts.
    const delay = count >= TURNS.length ? 4200 : 1500;
    const timer = setTimeout(() => setCount((current) => (current >= TURNS.length ? 1 : current + 1)), delay);
    return () => clearTimeout(timer);
  }, [count, inView, reduced]);

  const shown = reduced ? TURNS.length : count;
  const turns = TURNS.slice(0, shown);
  const last = turns[turns.length - 1];
  const ended = shown >= TURNS.length;
  const round = Math.ceil(shown / 2);

  return (
    <section ref={ref} aria-label="Sample match" className="border border-line-strong bg-card">
      <p className="sr-only">
        Sample match, replayed on a loop. The buyer opens at MYR 668 and the seller at MYR 1,288. They trade offers for ten turns,
        the referee nudging prices toward lucky numbers, and settle at MYR 768.
      </p>
      <div aria-hidden>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-4 py-3 sm:px-6">
          <Badge className={`h-auto gap-2 rounded-sm px-2 py-0.5 font-display text-lg font-bold uppercase text-white ${ended ? "bg-line-strong" : "bg-live"}`}>
            {!ended && <span className="size-2 animate-pulse rounded-full bg-white motion-reduce:animate-none" />}
            {ended ? "Full time" : "Live"}
          </Badge>
          <p className="min-w-0 flex-1 truncate text-lg font-medium">Vintage Yamaha guitar</p>
          <p className="w-full text-sm tabular-nums text-muted-foreground sm:w-auto">Round {round} of {ROUNDS} · MYR · Sample match</p>
        </div>

        <div className="px-4 pt-5 sm:px-6">
          <div className="grid grid-cols-2 gap-6 sm:gap-12">
            <Team side="buyer" price={last.bid} face={last.buyerFace} label="Current bid" />
            <Team side="seller" price={last.ask} face={last.sellerFace} label="Current ask" />
          </div>

          <div className="mt-5 flex items-baseline justify-between gap-4">
            <p className="font-display text-xl font-bold uppercase">Gap</p>
            <p className="font-display text-3xl font-bold tabular-nums"><RollingNumber value={last.ask - last.bid} /></p>
          </div>
          <div className="mt-2">
            <div className="relative h-5 bg-line">
              <motion.div
                className="absolute inset-y-0 bg-foreground/15"
                initial={false}
                animate={{ left: `${position(last.bid)}%`, right: `${100 - position(last.ask)}%` }}
                transition={{ duration: 0.8, ease: EASE }}
              />
              <motion.div className="absolute -inset-y-1.5 w-1.5 -translate-x-1/2 bg-buyer" initial={false} animate={{ left: `${position(last.bid)}%` }} transition={{ duration: 0.8, ease: EASE }} />
              <motion.div className="absolute -inset-y-1.5 w-1.5 -translate-x-1/2 bg-seller" initial={false} animate={{ left: `${position(last.ask)}%` }} transition={{ duration: 0.8, ease: EASE }} />
            </div>
            <div className="mt-3 flex justify-between text-sm tabular-nums text-muted-foreground">
              <span>First bid {money(FIRST_BID)}</span>
              <span>Opening ask {money(OPENING_ASK)}</span>
            </div>
          </div>

          <div className="mt-4 h-12 sm:h-14">
            <AnimatePresence initial={false}>
              {ended && (
                <motion.div
                  key="deal"
                  initial={reduced ? false : { opacity: 0, clipPath: "inset(0 100% 0 0)" }}
                  animate={{ opacity: 1, clipPath: "inset(0 0% 0 0)" }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.7, ease: EASE }}
                  className="flex h-full items-center bg-referee px-4 text-referee-ink"
                >
                  <p className="font-display text-3xl font-bold uppercase leading-none sm:text-5xl">Deal at MYR {money(last.price)}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <ol className="min-h-[14.5rem] px-4 pb-3 sm:px-6">
          {turns.slice(-3).map((turn) => {
            const index = TURNS.indexOf(turn);
            return (
              <motion.li
                key={index}
                initial={reduced ? false : { opacity: 0, x: turn.side === "buyer" ? -28 : 28, filter: "blur(4px)" }}
                animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                transition={{ duration: 0.45, ease: EASE }}
                className="grid grid-cols-[5.5rem_1fr_auto] items-baseline gap-x-4 border-t border-line py-3"
              >
                <p className={`font-display text-lg font-bold uppercase ${sideText[turn.side]}`}>{turn.side}</p>
                <div>
                  <p className="text-lg leading-snug">{line(turn)}</p>
                  {turn.note && (
                    <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                      <Sparkles aria-hidden className="size-3.5" /> {turn.note}
                    </p>
                  )}
                </div>
                <p className="font-display text-2xl font-bold tabular-nums">{money(turn.price)}</p>
              </motion.li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
