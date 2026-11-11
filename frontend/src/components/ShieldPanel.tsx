"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Ban, Check, ExternalLink, Lock, PackageCheck, RotateCcw, Truck, Wallet, type LucideIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useShield, type ShieldState, type ShieldView } from "@/lib/useShield";

const EASE = [0.16, 1, 0.3, 1] as const;

const STEPS: { state: ShieldState; label: string; icon: LucideIcon }[] = [
  { state: "negotiated", label: "Agreed", icon: Check },
  { state: "authorized", label: "Held", icon: Lock },
  { state: "shipped", label: "Shipped", icon: Truck },
  { state: "delivered", label: "Delivered", icon: PackageCheck },
  { state: "captured", label: "Paid", icon: Wallet },
];

const LOG_TEXT: Record<string, string> = {
  approve: "Buyer approved the hold",
  authorize: "Funds held. Seller not paid yet",
  ship: "Seller shipped with tracking",
  deliver: "Delivery confirmed",
  capture: "Funds released to the seller",
  cancel: "Deal cancelled. Hold released",
  expire: "Deadline missed. Hold released",
  refund: "Buyer refunded",
};

export function headline(view: ShieldView): string {
  const money = `${view.currency} ${(view.amount_minor / 100).toLocaleString("en-US")}`;
  switch (view.state) {
    case "negotiated":
      return `${money} agreed. No money has moved.`;
    case "authorized":
      return `${money} on hold. The seller can't touch it yet.`;
    case "shipped":
      return `${money} still on hold until delivery is confirmed.`;
    case "delivered":
      return "Delivery confirmed, but the payment hasn't gone through.";
    case "captured":
      return `${money} paid to the seller.`;
    case "refunded":
      return `${money} refunded to the buyer.`;
    case "voided":
      return `Hold released. The buyer keeps ${money}.`;
  }
}

export function Tracker({ state, shipped }: { state: ShieldState; shipped: boolean }) {
  const reduced = useReducedMotion();
  // A voided hold was authorized at least, and was shipped if a tracking number was recorded.
  const reached =
    state === "refunded" ? STEPS.length - 1 : state === "voided" ? (shipped ? 2 : 1) : STEPS.findIndex((step) => step.state === state);
  const progress = Math.max(reached, 0) / (STEPS.length - 1);
  return (
    <div className="relative">
      <div className="absolute inset-x-[10%] top-5 h-1 bg-line" aria-hidden>
        <motion.div
          className="h-full origin-left bg-referee"
          initial={false}
          animate={{ scaleX: progress }}
          transition={reduced ? { duration: 0 } : { duration: 0.9, ease: EASE }}
        />
      </div>
      <ol className="relative grid grid-cols-5">
        {STEPS.map((step, index) => {
          const done = index <= reached;
          const current = state === step.state;
          // After a refund the last step tells the truth instead of still saying "Paid".
          const refunded = state === "refunded" && index === STEPS.length - 1;
          const Icon = refunded ? RotateCcw : step.icon;
          return (
            <li key={step.state} aria-current={current ? "step" : undefined} className="grid justify-items-center gap-2 text-center">
              <motion.span
                initial={false}
                animate={{ scale: current && !reduced ? [1, 1.25, 1] : 1 }}
                transition={{ duration: 0.5, ease: EASE }}
                className={`grid size-11 place-items-center rounded-full border-2 transition-colors duration-500 ${done ? "border-referee bg-referee text-referee-ink" : "border-line-strong bg-background text-muted-foreground"}`}
              >
                <Icon className="size-5" aria-hidden />
              </motion.span>
              <span className={`text-sm ${done ? "font-semibold" : "text-muted-foreground"}`}>{refunded ? "Refunded" : step.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function ShieldPanel({ dealId }: { dealId: string }) {
  const { view, log, act } = useShield(dealId, true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approveUrl, setApproveUrl] = useState<string | null>(null);
  const [tracking, setTracking] = useState("");
  const reduced = useReducedMotion();

  async function run(step: string, body?: object) {
    setBusy(true);
    setError(null);
    try {
      return await act(step, body);
    } catch (caught) {
      setError(caught instanceof TypeError ? "Can't reach the API. Check it's running and try again." : (caught as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    const result = await run("approve");
    if (!result) return;
    if (result.approve_url) setApproveUrl(result.approve_url);
    else await run("authorize");
  }

  async function ship(event: FormEvent) {
    event.preventDefault();
    await run("ship", { tracking_number: tracking.trim() });
  }

  if (!view) return null;
  const state = view.state;
  const canCancel = state === "authorized" || state === "shipped";

  return (
    <motion.section
      aria-labelledby="shield-heading"
      initial={reduced ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: EASE }}
      className="border-b border-line px-4 py-8 sm:px-8"
    >
      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1.5fr_1fr] lg:gap-14">
        <div className="grid content-start gap-7">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 id="shield-heading" className="font-display text-3xl font-bold uppercase">Kena Scam Shield</h2>
              <Badge variant="outline" className="border-line-strong">
                {view.gateway === "simulated" ? "Simulated payments" : "PayPal sandbox"}
              </Badge>
            </div>
            <AnimatePresence mode="wait">
              <motion.p
                key={state}
                aria-live="polite"
                initial={reduced ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, y: -8 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="mt-2 text-xl text-balance"
              >
                {headline(view)}
              </motion.p>
            </AnimatePresence>
          </div>

          <Tracker state={state} shipped={Boolean(view.tracking_number)} />

          {error && (
            <Alert variant="destructive" className="border-live/60 bg-live/15 text-foreground">
              <AlertDescription className="text-foreground">{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-wrap items-end gap-3">
            {state === "negotiated" && !approveUrl && (
              <Button size="lg" disabled={busy} onClick={approve} className="bg-referee text-referee-ink hover:bg-referee/85">
                <Lock aria-hidden /> Approve hold
              </Button>
            )}
            {state === "negotiated" && approveUrl && (
              <>
                <Button size="lg" variant="outline" render={<a href={approveUrl} target="_blank" rel="noreferrer" />} nativeButton={false}>
                  <ExternalLink aria-hidden /> Approve on PayPal
                </Button>
                <Button size="lg" disabled={busy} onClick={() => run("authorize")} className="bg-referee text-referee-ink hover:bg-referee/85">
                  I&apos;ve approved it
                </Button>
              </>
            )}
            {state === "authorized" && (
              <form onSubmit={ship} className="flex flex-wrap items-end gap-3">
                <div className="grid gap-2">
                  <Label htmlFor="tracking">Tracking number</Label>
                  <Input id="tracking" required maxLength={64} value={tracking} onChange={(event) => setTracking(event.target.value)} className="h-10 w-56" placeholder="EE123456789MY" />
                </div>
                <Button size="lg" type="submit" disabled={busy || !tracking.trim()} className="bg-referee text-referee-ink hover:bg-referee/85">
                  <Truck aria-hidden /> Mark as shipped
                </Button>
              </form>
            )}
            {state === "shipped" && (
              <Button size="lg" disabled={busy} onClick={() => run("deliver")} className="bg-referee text-referee-ink hover:bg-referee/85">
                <PackageCheck aria-hidden /> Confirm delivery and pay
              </Button>
            )}
            {state === "delivered" && (
              <Button size="lg" disabled={busy} onClick={() => run("capture")} className="bg-referee text-referee-ink hover:bg-referee/85">
                <RotateCcw aria-hidden /> Retry payment
              </Button>
            )}
            {canCancel && (
              <Button size="lg" variant="outline" disabled={busy} onClick={() => run("cancel")}>
                <Ban aria-hidden /> Cancel and release hold
              </Button>
            )}
            {state === "captured" && (
              <Button size="lg" variant="outline" disabled={busy} onClick={() => run("refund")}>
                <RotateCcw aria-hidden /> Refund buyer
              </Button>
            )}
          </div>
        </div>

        <div>
          <h3 className="font-display text-xl font-bold uppercase">Money trail</h3>
          {log.length === 0 && <p className="mt-3 text-muted-foreground">Nothing yet. The trail starts when the buyer approves.</p>}
          <ol className="mt-3 grid gap-3 border-l-2 border-line pl-4">
            <AnimatePresence initial={false}>
              {log.map((entry) => (
                <motion.li
                  key={entry.id}
                  layout={!reduced}
                  initial={reduced ? false : { opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.35, ease: EASE }}
                >
                  {LOG_TEXT[entry.view.step] ?? entry.view.step}
                  {entry.view.step === "ship" && entry.view.tracking_number && (
                    <span className="block text-sm tabular-nums text-muted-foreground">{entry.view.tracking_number}</span>
                  )}
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>
        </div>
      </div>
    </motion.section>
  );
}
