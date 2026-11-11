"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Gavel, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type CSSProperties } from "react";
import { RollingNumber } from "@/components/RollingNumber";
import { ShieldPanel } from "@/components/ShieldPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  currentRound,
  leadingSeat,
  meterPosition,
  refereeCall,
  seatIndex,
  seatsOf,
  warHeadline,
  type Match,
  type Seat,
  type Turn,
} from "@/lib/negotiation";
import type { Connection } from "@/lib/useMatch";

const EASE = [0.16, 1, 0.3, 1] as const;
const money = (value: number | null) => (value === null ? "--" : value.toLocaleString("en-US"));

// Full class names, so Tailwind can see them. The first buyer is the same blue as a lone buyer.
const TEXT = ["text-bidder-1", "text-bidder-2", "text-bidder-3", "text-bidder-4"];
const BAR = ["bg-bidder-1", "bg-bidder-2", "bg-bidder-3", "bg-bidder-4"];
const TOP = ["border-bidder-1", "border-bidder-2", "border-bidder-3", "border-bidder-4"];

const STATE_LABEL: Partial<Record<Seat["state"], string>> = {
  walked: "Walked away",
  thrown_out: "Thrown out",
  won: "Winner",
};

function Lane({ seat, index, leading }: { seat: Seat; index: number; leading: boolean }) {
  const out = seat.state === "walked" || seat.state === "thrown_out";
  const reduced = useReducedMotion();
  return (
    <div className={`border-t-4 px-3 pb-4 pt-3 transition-opacity duration-500 ${TOP[index]} ${out ? "opacity-45" : ""} ${leading || seat.state === "won" ? "bg-card" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <p className={`font-display text-2xl font-bold uppercase leading-none ${TEXT[index]}`}>{seat.name}</p>
        <AnimatePresence mode="popLayout" initial={false}>
          {(leading || STATE_LABEL[seat.state]) && (
            <motion.span
              key={seat.state + String(leading)}
              initial={reduced ? false : { opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: EASE }}
            >
              <Badge
                className={`h-auto rounded-sm px-1.5 py-0.5 text-sm font-semibold ${
                  seat.state === "thrown_out" || seat.state === "walked" ? "bg-live text-white" : "bg-referee text-referee-ink"
                }`}
              >
                {STATE_LABEL[seat.state] ?? "Leading"}
              </Badge>
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <p className="mt-1 font-display text-5xl font-bold leading-none tabular-nums sm:text-6xl">
        <RollingNumber value={seat.bid} />
      </p>
      <div className="mt-3 grid gap-2 text-sm text-muted-foreground">
        <Gauge label="Face" value={seat.face} bar={BAR[index]} />
        <Gauge label="Seller's patience" value={seat.patience} bar={seat.patience < 40 ? "bg-live" : "bg-seller"} tick />
      </div>
    </div>
  );
}

function Gauge({ label, value, bar, tick = false }: { label: string; value: number; bar: string; tick?: boolean }) {
  return (
    <div>
      <div className="flex justify-between">
        <span>{label}</span>
        <span className="tabular-nums text-foreground">{value}</span>
      </div>
      <div role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} className="relative mt-1 h-1.5 bg-line">
        <motion.div className={`h-full ${bar}`} initial={false} animate={{ width: `${value}%` }} transition={{ duration: 0.6, ease: EASE }} />
        {tick && <span aria-hidden className="absolute -inset-y-0.5 w-px bg-foreground/60" style={{ left: "30%" }} />}
      </div>
    </div>
  );
}

function BidMeter({ seats, ask, openingAsk }: { seats: Seat[]; ask: number | null; openingAsk: number }) {
  const low = Math.floor(openingAsk * 0.2);
  const transition = { duration: 0.8, ease: EASE };
  const lead = leadingSeat(seats);
  return (
    <div role="img" aria-label={`Bids against an ask of ${money(ask)}`}>
      <div className="relative h-5 bg-line">
        {lead?.bid != null && ask !== null && (
          <motion.div
            className="absolute inset-y-0 bg-foreground/15"
            initial={false}
            animate={{ left: `${meterPosition(lead.bid, low, openingAsk)}%`, right: `${100 - meterPosition(ask, low, openingAsk)}%` }}
            transition={transition}
          />
        )}
        {seats.map((seat, i) =>
          seat.bid === null ? null : (
            <motion.div
              key={seat.id}
              className={`absolute -inset-y-1.5 w-1.5 -translate-x-1/2 ${BAR[i]} ${seat.state === "walked" || seat.state === "thrown_out" ? "opacity-40" : ""}`}
              initial={false}
              animate={{ left: `${meterPosition(seat.bid, low, openingAsk)}%` }}
              transition={transition}
            />
          ),
        )}
        {ask !== null && (
          <motion.div className="absolute -inset-y-1.5 w-1.5 -translate-x-1/2 bg-seller" initial={false} animate={{ left: `${meterPosition(ask, low, openingAsk)}%` }} transition={transition} />
        )}
      </div>
      <div className="mt-3 flex justify-between text-sm tabular-nums text-muted-foreground">
        <span aria-hidden />
        <span>Opening ask {money(openingAsk)}</span>
      </div>
    </div>
  );
}

function Move({ turn, match }: { turn: Turn; match: Match }) {
  const reduced = useReducedMotion();
  const buyer = turn.side === "buyer";
  const index = seatIndex(match, turn.bidder);
  const call = refereeCall(turn, match.currency);
  const out = Boolean(turn.note && /^(Thrown out|Walked)/.test(turn.note));
  return (
    <motion.li
      initial={reduced ? false : { opacity: 0, x: buyer ? -28 : 28, filter: "blur(4px)" }}
      animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.45, ease: EASE }}
      className="grid grid-cols-[auto_1fr] gap-x-4 border-t border-line py-4 sm:grid-cols-[9rem_1fr_auto]"
    >
      <div>
        <p className={`font-display text-lg font-bold uppercase leading-tight ${buyer ? TEXT[index] : "text-seller"}`}>{buyer ? turn.bidder_name : "Seller"}</p>
        {!buyer && turn.bidder_name && <p className="text-sm text-muted-foreground">to {turn.bidder_name}</p>}
      </div>
      <div className="col-span-2 row-start-2 sm:col-span-1 sm:row-start-auto">
        <p className="text-lg leading-snug">{turn.message}</p>
        {call?.kind === "overruled" && (
          <Badge className="mt-2 h-auto gap-1.5 whitespace-normal rounded-sm bg-referee px-2 py-1 text-sm font-semibold text-referee-ink">
            <Gavel aria-hidden className="size-3.5" /> Referee: {call.text}
          </Badge>
        )}
        {call?.kind === "snapped" && (
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
            <Sparkles aria-hidden className="size-3.5" /> {call.text}
          </p>
        )}
        {turn.note && (
          <Badge className={`mt-2 h-auto whitespace-normal rounded-sm px-2 py-1 text-sm font-semibold ${out ? "bg-live text-white" : "bg-referee text-referee-ink"}`}>
            {turn.note}
          </Badge>
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

export function BiddingWar({ dealId, match, connection }: { dealId: string; match: Match; connection: Connection }) {
  const reduced = useReducedMotion();
  const feedEnd = useRef<HTMLLIElement>(null);
  const seats = seatsOf(match);
  const last = match.turns.at(-1);
  const lead = leadingSeat(seats);
  const ask = last?.last_ask ?? match.openingAsk;
  const label = status(connection, Boolean(match.ended));

  useEffect(() => {
    const behavior = reduced ? "auto" : "smooth";
    if (match.ended) window.scrollTo({ top: 0, behavior });
    else if (match.turns.length > 0) feedEnd.current?.scrollIntoView({ behavior, block: "end" });
  }, [match.turns.length, match.ended, reduced]);

  return (
    <main className="min-h-dvh pb-16">
      <header className={`border-b border-line bg-background px-4 py-4 sm:px-8 ${match.ended ? "" : "lg:sticky lg:top-0 lg:z-10"}`}>
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <Badge aria-live="polite" className={`h-auto gap-2 rounded-sm px-2 py-0.5 font-display text-lg font-bold uppercase text-white ${match.ended ? "bg-line-strong" : "bg-live"}`}>
              {!match.ended && <span className="size-2 animate-pulse rounded-full bg-white motion-reduce:animate-none" />}
              {label}
            </Badge>
            <h1 className="min-w-0 flex-1 truncate text-lg font-medium">{match.item || "Loading the bidding war"}</h1>
            <p className="w-full text-sm tabular-nums text-muted-foreground sm:w-auto">
              Bidding war · {match.maxRounds > 0 && `Round ${currentRound(match)} of ${match.maxRounds} · `}{match.currency}
            </p>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-6 sm:gap-12">
            <div>
              <p className="font-display text-xl font-bold uppercase text-seller sm:text-2xl">Seller asks</p>
              <p className="font-display text-5xl font-bold leading-none tabular-nums sm:text-7xl"><RollingNumber value={ask} /></p>
            </div>
            <div className="text-right">
              <p className={`font-display text-xl font-bold uppercase sm:text-2xl ${lead ? TEXT[seatIndex(match, lead.id)] : "text-muted-foreground"}`}>
                {lead ? `${lead.name} ${lead.state === "won" ? "wins" : "leads"}` : "Leading bid"}
              </p>
              <p className="font-display text-5xl font-bold leading-none tabular-nums sm:text-7xl"><RollingNumber value={lead?.bid ?? null} /></p>
            </div>
          </div>

          <div
            className="mt-5 grid grid-cols-2 gap-x-5 gap-y-4 lg:[grid-template-columns:repeat(var(--n),minmax(0,1fr))]"
            style={{ "--n": Math.max(2, seats.length) } as CSSProperties}
          >
            {seats.map((seat, i) => (
              <Lane key={seat.id} seat={seat} index={i} leading={lead?.id === seat.id && !match.ended} />
            ))}
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
                <h2 className="font-display text-4xl font-bold uppercase leading-none sm:text-6xl">{warHeadline(match.ended, match.currency)}</h2>
                <Button variant="link" className="h-auto p-0 text-inherit underline" nativeButton={false} render={<Link href="/play" />}>Start another match</Button>
              </motion.section>
            )}
          </AnimatePresence>

          {match.openingAsk !== null && (
            <div className="mt-5 pb-1">
              <BidMeter seats={seats} ask={ask} openingAsk={match.openingAsk} />
            </div>
          )}
        </div>
      </header>

      {match.ended?.status === "deal" && <ShieldPanel dealId={dealId} />}

      <div className="mx-auto max-w-6xl px-4 pt-6 sm:px-8">
        <h2 className="sr-only">Commentary</h2>
        {match.turns.length === 0 && <p className="py-8 text-lg text-muted-foreground">Waiting for the first bids.</p>}
        <ol aria-live="polite">
          {match.turns.map((turn, i) => (
            <div key={turn.turn} className="contents">
              {turn.round !== undefined && turn.round !== match.turns[i - 1]?.round && (
                <li aria-hidden className="pb-1 pt-6 font-display text-xl font-bold uppercase text-muted-foreground">
                  {turn.round === match.maxRounds ? "Final round: sealed bids" : `Round ${turn.round}`}
                </li>
              )}
              <Move turn={turn} match={match} />
            </div>
          ))}
          <li ref={feedEnd} aria-hidden />
        </ol>
      </div>
    </main>
  );
}
