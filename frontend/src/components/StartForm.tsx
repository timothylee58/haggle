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
  { value: "malaysian_chinese", label: "Malaysian-Chinese: favours 8, refuses 444" },
  { value: "neutral", label: "Neutral: no lucky numbers" },
];

function Field({ label, name, defaultValue, hint }: { label: string; name: string; defaultValue: number; hint?: string }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} className={inputClass} name={name} type="number" min={1} max={10000000} step={1} required defaultValue={defaultValue} inputMode="numeric" />
      {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
    </div>
  );
}

function explain(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  return "The match could not start. Check the prices and try again.";
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
        <div className="grid gap-2">
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
          <AlertDescription className="text-foreground">{error}</AlertDescription>
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
