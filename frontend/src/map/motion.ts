import { useEffect, useRef, useState } from "react";

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const easeOutCubic = (t: number) => 1 - (1 - t) ** 3;

/** Animates a number towards `target` (instantly under reduced motion). */
export function useCountUp(target: number | null, duration = 900): number | null {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);

  useEffect(() => {
    if (target === null) {
      setValue(null);
      fromRef.current = null;
      return;
    }
    const from = fromRef.current ?? target;
    if (from === target || prefersReducedMotion()) {
      setValue(target);
      fromRef.current = target;
      return;
    }
    let frame = 0;
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const v = from + (target - from) * easeOutCubic(t);
      setValue(v);
      fromRef.current = v;
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}

/** Runs `onFrame(t)` for t in 0..1 over `duration` ms; returns a cancel function. */
export function tween(duration: number, onFrame: (t: number) => void, onDone?: () => void) {
  if (prefersReducedMotion()) {
    onFrame(1);
    onDone?.();
    return () => {};
  }
  let frame = 0;
  const start = performance.now();
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / duration);
    onFrame(easeOutCubic(t));
    if (t < 1) frame = requestAnimationFrame(step);
    else onDone?.();
  };
  frame = requestAnimationFrame(step);
  return () => cancelAnimationFrame(frame);
}
