"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { API_URL } from "@/lib/useMatch";

const inputClass = "h-11 bg-field text-base tabular-nums";

const HOUSE_RULES = [
  { value: "malaysian_chinese", label: "Malaysian-Chinese", hint: "Favours 8, refuses 4." },
  { value: "neutral", label: "Neutral", hint: "No lucky or unlucky numbers." },
];

const FIELD_NAMES: Record<string, string> = {
  opening_ask: "opening ask",
  seller_floor: "lowest price",
  budget_cap: "budget cap",
  max_rounds: "rounds",
  item: "item",
};

function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function Field({ label, name, defaultValue, hint }: { label: string; name: string; defaultValue: number; hint?: string }) {
  return (
    <div className="grid content-start gap-2">
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} className={inputClass} name={name} type="number" min={1} max={10000000} step={1} required defaultValue={defaultValue} inputMode="numeric" />
      {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Turns an API validation error into a plain sentence that uses the form's own labels. */
function explain(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) {
    const first = detail[0] as { msg: string; loc?: unknown[] };
    const message = first.msg
      .replace(/^Value error, /, "")
      .replace(/opening_ask|seller_floor|budget_cap|max_rounds/g, (name) => FIELD_NAMES[name]);
    const field = typeof first.loc?.[1] === "string" ? FIELD_NAMES[first.loc[1]] : undefined;
    return field ? `${sentence(field)}: ${message.charAt(0).toLowerCase()}${message.slice(1)}` : sentence(message);
  }
  return "The match could not start. Check the prices and try again.";
}

/** Catches the mistake we can see before any request is sent. */
function checkPrices(floor: number, ask: number): string | null {
  return ask < floor ? "The opening ask can't be below the lowest price." : null;
}

export function StartForm() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [culture, setCulture] = useState("malaysian_chinese");
  const [useLlm, setUseLlm] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const problem = checkPrices(Number(data.get("seller_floor")), Number(data.get("opening_ask")));
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/negotiations`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          item: data.get("item"),
          budget_cap: Number(data.get("budget_cap")),
          seller_floor: Number(data.get("seller_floor")),
          opening_ask: Number(data.get("opening_ask")),
          culture,
          max_rounds: Number(data.get("max_rounds")),
          use_llm: useLlm,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(explain(body.detail));
      router.push(`/deals/${body.deal_id}`);
    } catch (caught) {
      const offline = caught instanceof TypeError;
      setError(offline ? `Can't reach the API at ${API_URL}. Start it and try again.` : (caught as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-8">
      <div className="grid gap-2">
        <Label htmlFor="item">What&apos;s being sold</Label>
        <Input id="item" className={inputClass} name="item" required maxLength={200} defaultValue="Vintage Yamaha guitar" />
      </div>

      <div className="grid gap-8 sm:grid-cols-2">
        <fieldset className="grid content-start gap-4 border-t-4 border-buyer pt-4">
          <legend className="sr-only">Buyer</legend>
          <p aria-hidden className="font-display text-2xl font-bold uppercase text-buyer">Buyer</p>
          <Field label="Budget cap" name="budget_cap" defaultValue={950} hint="Enforced in code. Hidden from spectators." />
        </fieldset>
        <fieldset className="grid content-start gap-4 border-t-4 border-seller pt-4">
          <legend className="sr-only">Seller</legend>
          <p aria-hidden className="font-display text-2xl font-bold uppercase text-seller">Seller</p>
          <Field label="Opening ask" name="opening_ask" defaultValue={1288} />
          <Field label="Lowest price" name="seller_floor" defaultValue={700} hint="Enforced in code. Hidden from spectators." />
        </fieldset>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="grid min-w-0 content-start gap-2">
          <Label>House rules</Label>
          <Select items={HOUSE_RULES} value={culture} onValueChange={(value) => setCulture(value ?? "neutral")}>
            <SelectTrigger className="h-11! w-full bg-field text-base">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {HOUSE_RULES.map((rule) => (
                <SelectItem key={rule.value} value={rule.value}>{rule.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground">{HOUSE_RULES.find((rule) => rule.value === culture)?.hint}</p>
        </div>
        <Field label="Rounds" name="max_rounds" defaultValue={6} />
      </div>

      <div className="flex items-start gap-3">
        <Switch id="use_llm" checked={useLlm} onCheckedChange={setUseLlm} className="mt-0.5" />
        <div className="grid gap-1">
          <Label htmlFor="use_llm">Let Claude play both sides</Label>
          <p className="text-sm text-muted-foreground">Off runs rule-based agents with no API key.</p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="border-live/60 bg-live/15">
          <AlertDescription className="text-foreground! text-base">{error}</AlertDescription>
        </Alert>
      )}

      <motion.div whileHover={busy ? undefined : { scale: 1.01 }} whileTap={busy ? undefined : { scale: 0.98 }}>
        <Button type="submit" disabled={busy} className="h-14 w-full rounded-md bg-live font-display text-2xl font-bold uppercase text-white hover:bg-live/85">
          {busy && <Loader2 aria-hidden className="animate-spin" />}
          {busy ? "Starting" : "Start the match"}
        </Button>
      </motion.div>
    </form>
  );
}
