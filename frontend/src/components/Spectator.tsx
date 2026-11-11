"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Gavel, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { RollingNumber } from "@/components/RollingNumber";
import { BiddingWar } from "@/components/BiddingWar";
import { ShieldPanel } from "@/components/ShieldPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { currentRound, meterPosition, refereeCall, resultHeadline, type Match, type Side, type Turn } from "@/lib/negotiation";
import { useMatch, type Connection } from "@/lib/useMatch";

const EASE = [0.16, 1, 0.3, 1] as const;
const money = (value: number | null) => (value === null ? "--" : value.toLocaleString("en-US"));
const sideText: Record<Side, string> = { buyer: "text-buyer", seller: "text-seller" };
const sideBar: Record<Side, string> = { buyer: "bg-buyer", seller: "bg-seller" };

function Face({ side, score, delta, turn }: { side: Side; score: number; delta: number; turn: number }) {
  const reduced = useReducedMotion();
  return (
    <div className="mt-3">
      <div className="flex justify-between text-sm text-muted-foreground">
        <span className="flex items-center gap-2">
          Face
          <AnimatePresence mode="popLayout">
            {delta !== 0 && (
              <motion.span
                key={turn}
                initial={reduced ? false : { opacity: 0, y: 8, scale: 0.8 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3, ease: EASE }}
                className={`font-semibold tabular-nums ${delta > 0 ? "text-referee" : "text-seller"}`}
              >
                {delta > 0 ? `+${delta}` : `−${Math.abs(delta)}`}
              </motion.span>
            )}
          </AnimatePresence>
        </span>
        <span className="tabular-nums text-foreground">{score}</span>
      </div>
      <div role="meter" aria-label={`${side} face`} aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} className="mt-1 h-1.5 overflow-hidden bg-line">
        <motion.div className={`h-full ${sideBar[side]}`} initial={false} animate={{ width: `${score}%` }} transition={{ duration: 0.6, ease: EASE }} />
      </div>
    </div>
  );
}

function Team({ side, price, face, label, delta, turn, onMove }: { side: Side; price: number | null; face: number; label: string; delta: number; turn: number; onMove: boolean }) {
  return (
    <div className={side === "seller" ? "sm:text-right" : ""}>
      <p className={`inline-flex items-center gap-2 font-display text-xl font-bold uppercase sm:text-2xl ${sideText[side]}`}>
        {side}
        {onMove && <motion.span layoutId="possession" aria-hidden className={`size-2 rounded-full ${sideBar[side]}`} />}
      </p>
      <p className="font-display text-5xl font-bold leading-none tabular-nums sm:text-7xl lg:text-8xl"><RollingNumber value={price} /></p>
      <p className="mt-1 text-sm text-muted-foreground">{label}</p>
      <Face side={side} score={face} delta={delta} turn={turn} />
    </div>
  );
}

function Meter({ match, last }: { match: Match; last: Turn | undefined }) {
  const low = match.firstBid;
  const high = match.openingAsk;
  const ready = low !== null && high !== null && last?.last_bid != null && last?.last_ask != null;
  const bid = ready ? meterPosition(last.last_bid!, low, high) : 0;
  const ask = ready ? meterPosition(last.last_ask!, low, high) : 100;
  const transition = { duration: 0.8, ease: EASE };
  return (
    <div aria-label={ready ? `Price gap ${match.currency} ${money(last.gap)}` : "Price gap, waiting for the first bid"} role="img">
      <div className="relative h-5 bg-line">
        <motion.div className="absolute inset-y-0 bg-foreground/15" initial={false} animate={{ left: `${bid}%`, right: `${100 - ask}%` }} transition={transition} />
        <motion.div className="absolute -inset-y-1.5 w-1.5 -translate-x-1/2 bg-buyer" initial={false} animate={{ left: `${bid}%` }} transition={transition} />
        <motion.div className="absolute -inset-y-1.5 w-1.5 -translate-x-1/2 bg-seller" initial={false} animate={{ left: `${ask}%` }} transition={transition} />
      </div>
      <div className="mt-3 flex justify-between text-sm tabular-nums text-muted-foreground">
        <span>First bid {money(low)}</span>
        <span>Opening ask {money(high)}</span>
      </div>
    </div>
  );
}

function Commentary({ turn, currency }: { turn: Turn; currency: string }) {
  const reduced = useReducedMotion();
  const call = refereeCall(turn, currency);
  return (
    <motion.li
      initial={reduced ? false : { opacity: 0, x: turn.side === "buyer" ? -28 : 28, filter: "blur(4px)" }}
      animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.45, ease: EASE }}
      className="grid grid-cols-[auto_1fr] gap-x-4 border-t border-line py-4 sm:grid-cols-[6rem_1fr_auto]"
    >
      <p className={`font-display text-lg font-bold uppercase ${sideText[turn.side]}`}>{turn.side}</p>
      <div className="col-span-2 row-start-2 sm:col-span-1 sm:row-start-auto">
        <p className="text-lg leading-snug">{turn.message}</p>
        {call?.kind === "overruled" && (
          <motion.div
            initial={reduced ? false : { opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.25, duration: 0.3, ease: EASE }}
            className="mt-2 origin-left"
          >
            <Badge className="h-auto gap-1.5 whitespace-normal rounded-sm bg-referee px-2 py-1 text-sm font-semibold text-referee-ink">
              <Gavel aria-hidden className="size-3.5" /> Referee: {call.text}
            </Badge>
          </motion.div>
        )}
        {call?.kind === "snapped" && (
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
            <Sparkles aria-hidden className="size-3.5" /> {call.text}
          </p>
        )}
      </div>
      <p className="justify-self-end font-display text-2xl font-bold tabular-nums">{money(turn.price)}</p>
    </motion.li>
  );
}

function status(connection: Connection, ended: boolean): string {
  if (ended) return "Full time";
  if (connection === "reconnecting") return "Reconnecting";
  if (connection === "connecting") return "Connecting";
  return "Live";
}

export function Spectator({ dealId }: { dealId: string }) {
  const { match, connection } = useMatch(dealId);
  if (match.mode === "bidding_war") return <BiddingWar dealId={dealId} match={match} connection={connection} />;
  return <Duel dealId={dealId} match={match} connection={connection} />;
}

function Duel({ dealId, match, connection }: { dealId: string; match: Match; connection: Connection }) {
  const last = match.turns.at(-1);
  const feedEnd = useRef<HTMLLIElement>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    const behavior = reduced ? "auto" : "smooth";
    // At full time, return to the top: the result and the Shield live there.
    if (match.ended) window.scrollTo({ top: 0, behavior });
    else if (match.turns.length > 0) feedEnd.current?.scrollIntoView({ behavior, block: "end" });
  }, [match.turns.length, match.ended, reduced]);

  if (connection === "missing" && !match.item) {
    return (
      <main className="mx-auto grid min-h-dvh max-w-xl content-center gap-4 px-4">
        <h1 className="font-display text-5xl font-bold uppercase">Match not found</h1>
        <p className="text-muted-foreground">This link has no match behind it, or the API isn&apos;t reachable.</p>
        <Link href="/play" className="underline underline-offset-4">Start a new match</Link>
      </main>
    );
  }

  const previous = match.turns.at(-2);
  const label = status(connection, Boolean(match.ended));
  return (
    <main className="min-h-dvh pb-16">
      <header className={`border-b border-line bg-background px-4 py-4 sm:px-8 ${match.ended ? "" : "lg:sticky lg:top-0 lg:z-10"}`}>
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <Badge aria-live="polite" className={`h-auto gap-2 rounded-sm px-2 py-0.5 font-display text-lg font-bold uppercase text-white ${match.ended ? "bg-line-strong" : "bg-live"}`}>
              {!match.ended && <span className="size-2 animate-pulse rounded-full bg-white motion-reduce:animate-none" />}
              {label}
            </Badge>
            <h1 className="min-w-0 flex-1 truncate text-lg font-medium">{match.item || "Loading the match"}</h1>
            <p className="text-sm tabular-nums text-muted-foreground">
              {match.maxRounds > 0 && `Round ${currentRound(match)} of ${match.maxRounds} · `}{match.currency}
            </p>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-6 sm:gap-12">
            <Team side="buyer" price={last?.last_bid ?? null} face={last?.buyer_face ?? 70} label="Current bid" turn={last?.turn ?? 0} onMove={!match.ended && last?.side === "buyer"} delta={last && previous ? last.buyer_face - previous.buyer_face : 0} />
            <Team side="seller" price={last?.last_ask ?? match.openingAsk} face={last?.seller_face ?? 70} label="Current ask" turn={last?.turn ?? 0} onMove={!match.ended && last?.side === "seller"} delta={last && previous ? last.seller_face - previous.seller_face : (last ? last.seller_face - 70 : 0)} />
          </div>
          <AnimatePresence>
            {match.ended && (
              <motion.section
                aria-live="assertive"
                initial={reduced ? false : { opacity: 0, clipPath: "inset(0 100% 0 0)" }}
                animate={{ opacity: 1, clipPath: "inset(0 0% 0 0)" }}
                transition={{ duration: 0.7, ease: EASE }}
                className={`mt-5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-4 py-3 ${match.ended.status === "deal" ? "bg-referee text-referee-ink" : "bg-line text-foreground"}`}
              >
                <h2 className="font-display text-4xl font-bold uppercase leading-none sm:text-6xl">
                  {resultHeadline(match.ended.status, match.currency, match.ended.finalPrice)}
                </h2>
                <Button variant="link" className="h-auto p-0 text-inherit underline" nativeButton={false} render={<Link href="/play" />}>Start another match</Button>
              </motion.section>
            )}
          </AnimatePresence>
          <div className="mt-5 flex items-baseline justify-between gap-4">
            <p className="font-display text-xl font-bold uppercase">Gap</p>
            <p className="font-display text-3xl font-bold tabular-nums"><RollingNumber value={last?.gap ?? null} /></p>
          </div>
          <div className="mt-2 pb-1"><Meter match={match} last={last} /></div>
        </div>
      </header>

      {match.ended?.status === "deal" && <ShieldPanel dealId={dealId} />}

      <div className="mx-auto max-w-6xl px-4 pt-6 sm:px-8">
        <h2 className="sr-only">Commentary</h2>
        {match.turns.length === 0 && <p className="py-8 text-lg text-muted-foreground">Waiting for the buyer&apos;s opening bid.</p>}
        <ol aria-live="polite">
          {match.turns.map((turn) => <Commentary key={turn.turn} turn={turn} currency={match.currency} />)}
          <li ref={feedEnd} aria-hidden />
        </ol>
      </div>
    </main>
  );
}
