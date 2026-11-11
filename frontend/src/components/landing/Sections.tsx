import { ArrowRight, Ban, Gavel, Lock, PackageCheck, TimerOff } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Faq } from "./Faq";
import { FaceDemo } from "./FaceDemo";
import { ScoreboardDemo } from "./ScoreboardDemo";
import { ShieldDemo } from "./ShieldDemo";

const wrap = "mx-auto max-w-6xl px-4 sm:px-8";
const h2 = "font-display text-5xl font-bold uppercase leading-[0.92] text-balance sm:text-6xl";
const lead = "mt-5 max-w-prose text-lg leading-relaxed text-muted-foreground";
const startButton =
  "h-14 rounded-md bg-live px-8 font-display text-2xl font-bold uppercase text-white hover:bg-live/85";

export function Hero() {
  return (
    <section className={`${wrap} pb-16 pt-12 sm:pt-20`}>
      <h1 className="font-display text-6xl font-bold uppercase leading-[0.9] sm:text-8xl">
        <span className="text-buyer">Buyer</span>{" "}
        <span className="text-4xl text-muted-foreground sm:text-6xl">vs</span>{" "}
        <span className="text-seller">Seller</span>.
        <br />
        One price. Live.
      </h1>
      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
        <p className="max-w-xl text-xl leading-relaxed text-balance">
          Two AI agents haggle over a price while you watch. Code decides every number. The agents only do the talking.
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <Button nativeButton={false} render={<Link href="/play" />} className={startButton}>
            Start a match <ArrowRight aria-hidden className="size-6" />
          </Button>
          <Button
            variant="outline"
            nativeButton={false}
            render={<a href="#how" />}
            className="h-14 rounded-md border-line-strong px-6 text-base hover:bg-accent"
          >
            See how it works
          </Button>
        </div>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">No account needed. Payments run on PayPal&apos;s sandbox, so no real money moves.</p>
      <div className="mt-12">
        <ScoreboardDemo />
      </div>
    </section>
  );
}

const TICKER = [
  "Code decides the numbers",
  "The agents only do the talking",
  "Lucky 8s please the room",
  "Insulting numbers cost face",
  "Money moves only after delivery",
];

export function Ticker() {
  const row = TICKER.map((item) => (
    <span key={item} className="flex items-center gap-4 px-6">
      <span aria-hidden className="size-2.5 bg-referee" />
      {item}
    </span>
  ));
  return (
    <div className="overflow-hidden border-y border-line-strong py-3">
      <div className="ticker-track flex w-max font-display text-2xl font-bold uppercase motion-reduce:w-auto motion-reduce:flex-wrap">
        <div className="flex shrink-0 motion-reduce:flex-wrap">{row}</div>
        <div aria-hidden className="flex shrink-0 motion-reduce:hidden">{row}</div>
      </div>
    </div>
  );
}

const STEPS = [
  {
    title: "Set the stakes",
    text: "Pick the item, the buyer's budget and the seller's floor. Both limits stay hidden from the room and from the other agent.",
  },
  {
    title: "Watch the haggle",
    text: "The agents trade offers. The referee checks every price, nudges it toward lucky numbers and scores each move.",
  },
  {
    title: "Approve the hold",
    text: "When they shake hands, the buyer approves a hold on PayPal. The money is held, not taken.",
  },
  {
    title: "Delivery pays out",
    text: "The seller ships with tracking. Confirm delivery and the seller is paid. Cancel before then and the hold is released.",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className={`${wrap} scroll-mt-16 py-20 sm:py-28`}>
      <div className="grid gap-10 lg:grid-cols-[1fr_1.6fr] lg:gap-16">
        <div>
          <h2 className={h2}>Four steps from first bid to paid.</h2>
          <p className={lead}>No account, no setup. You can be watching a match in under a minute.</p>
          <Button nativeButton={false} render={<Link href="/play" />} className={`${startButton} mt-8`}>
            Start a match <ArrowRight aria-hidden className="size-6" />
          </Button>
        </div>
        <ol>
          {STEPS.map((step, index) => (
            <li key={step.title} className="grid grid-cols-[4.5rem_1fr] gap-4 border-t border-line-strong py-7 sm:grid-cols-[6rem_1fr] sm:gap-6">
              <span aria-hidden className="font-display text-6xl font-bold leading-none text-referee sm:text-7xl">{index + 1}</span>
              <div>
                <h3 className="font-display text-3xl font-bold uppercase">{step.title}</h3>
                <p className="mt-2 max-w-prose text-lg text-muted-foreground">{step.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Roles() {
  return (
    <section id="referee" className="scroll-mt-16 border-t border-line-strong py-20 sm:py-28">
      <div className={wrap}>
        <h2 className={h2}>Code decides. The AI talks.</h2>
        <p className={lead}>
          An agent can be Claude or a simple rule-based bot. Either way it only proposes a move and writes the banter. A referee
          written in plain code sets every price, so no model can agree to something outside the range.
        </p>
      </div>
      <div className={`${wrap} mt-12 grid gap-6 md:grid-cols-3`}>
        <article className="border-t-4 border-buyer pt-5">
          <h3 className="font-display text-5xl font-bold uppercase text-buyer">Buyer</h3>
          <p className="mt-3 text-lg text-muted-foreground">
            Opens low, concedes in small steps and treats its budget as a limit, not a target. Never reveals what it can pay.
          </p>
        </article>
        <article className="border-t-4 border-referee bg-referee p-5 text-referee-ink md:-mt-3 md:pb-9">
          <h3 className="font-display text-5xl font-bold uppercase">Referee</h3>
          <p className="mt-3 text-lg">
            No AI here, just code with the final say. It checks both limits, snaps prices to lucky numbers, scores face and
            overrules anything out of line.
          </p>
          <Badge className="mt-4 h-auto gap-1.5 whitespace-normal rounded-sm bg-referee-ink px-2 py-1 text-sm font-semibold text-referee">
            <Gavel aria-hidden className="size-3.5" /> Referee: MYR 798 became MYR 788
          </Badge>
        </article>
        <article className="border-t-4 border-seller pt-5">
          <h3 className="font-display text-5xl font-bold uppercase text-seller">Seller</h3>
          <p className="mt-3 text-lg text-muted-foreground">
            Holds its floor, trades concessions and walks away if it loses too much face. Never reveals its lowest price.
          </p>
        </article>
      </div>
    </section>
  );
}

export function FaceRules() {
  return (
    <section className={`${wrap} grid gap-10 border-t border-line-strong py-20 sm:py-28 lg:grid-cols-[1fr_1.1fr] lg:gap-16`}>
      <div>
        <h2 className={h2}>Lose face and the seller walks.</h2>
        <p className={lead}>
          Every move is scored. Respect earns face. Lowballs and unlucky numbers cost it, and a seller who drops below 30 leaves the
          table. Try it on the right.
        </p>
        <p className={lead}>
          In the Malaysian-Chinese house rules, 8 is lucky and 4 is avoided. The neutral rules turn the numbers off.
        </p>
      </div>
      <FaceDemo />
    </section>
  );
}

const LIMITS = [
  { icon: Lock, text: "No money moves until the buyer approves." },
  { icon: Ban, text: "No spending above the budget cap, checked at every payment." },
  { icon: PackageCheck, text: "No payment before delivery is confirmed." },
  { icon: TimerOff, text: "A missed deadline releases the hold." },
];

export function Shield() {
  return (
    <section id="shield" className="scroll-mt-16 border-t border-line-strong py-20 sm:py-28">
      <div className={`${wrap} grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:gap-16`}>
        <div>
          <h2 className={h2}>Your money moves only after delivery.</h2>
          <p className={lead}>
            Kena Scam Shield holds the payment while the goods are on their way. The buyer approves a hold, the seller ships with
            tracking, and only when the buyer confirms delivery does the payment go through.
          </p>
          <ul className="mt-8">
            {LIMITS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-4 border-t border-line py-4 text-lg">
                <Icon aria-hidden className="mt-1 size-5 shrink-0 text-referee" />
                {text}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-muted-foreground">Runs on PayPal&apos;s sandbox today, so no real money moves.</p>
        </div>
        <ShieldDemo />
      </div>
    </section>
  );
}

export function Questions() {
  return (
    <section id="faq" className={`${wrap} scroll-mt-16 grid gap-10 border-t border-line-strong py-20 sm:py-28 lg:grid-cols-[1fr_1.6fr] lg:gap-16`}>
      <h2 className={h2}>Before you start.</h2>
      <Faq />
    </section>
  );
}

export function FinalCta() {
  return (
    <section className="bg-referee py-20 text-referee-ink sm:py-28">
      <div className={`${wrap} grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end`}>
        <div>
          <h2 className="font-display text-6xl font-bold uppercase leading-[0.9] text-balance sm:text-8xl">Ready for the first bid?</h2>
          <p className="mt-5 max-w-prose text-xl">Set a budget, set a floor and let the agents go.</p>
        </div>
        <Button
          nativeButton={false}
          render={<Link href="/play" />}
          className="h-14 rounded-md bg-referee-ink px-8 font-display text-2xl font-bold uppercase text-referee hover:bg-referee-ink/85"
        >
          Start a match <ArrowRight aria-hidden className="size-6" />
        </Button>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className={`${wrap} flex flex-wrap items-center justify-between gap-x-8 gap-y-3 py-8`}>
        <p className="font-display text-3xl font-bold uppercase leading-none">Haggle</p>
        <p className="text-sm text-muted-foreground">Built for the PayPal AI Hackathon. Payments run on PayPal&apos;s sandbox.</p>
        <nav aria-label="Footer" className="flex gap-6 text-sm">
          <a href="#how" className="underline-offset-4 hover:underline">How it works</a>
          <Link href="/play" className="underline-offset-4 hover:underline">Start a match</Link>
        </nav>
      </div>
    </footer>
  );
}
