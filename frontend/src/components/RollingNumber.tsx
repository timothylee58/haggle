"use client";

import { useMotionValueEvent, useReducedMotion, useSpring } from "framer-motion";
import { useEffect, useState } from "react";

/** A price that rolls to its new value, shared by the live spectator and the landing demo. */
export function RollingNumber({ value }: { value: number | null }) {
  const reduced = useReducedMotion();
  const spring = useSpring(value ?? 0, { stiffness: 90, damping: 20 });
  const [shown, setShown] = useState(value ?? 0);
  useMotionValueEvent(spring, "change", (latest) => setShown(Math.round(latest)));
  useEffect(() => {
    if (value === null) return;
    if (reduced) spring.jump(value);
    else spring.set(value);
  }, [value, reduced, spring]);
  return <>{value === null ? "--" : shown.toLocaleString("en-US")}</>;
}
