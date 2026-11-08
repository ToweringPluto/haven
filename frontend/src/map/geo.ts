export type LngLat = [number, number];

/** Great-circle distance in metres. Straight line only: not a walking, cycling or transit route. */
export function straightLineMetres([lon1, lat1]: LngLat, [lon2, lat2]: LngLat): number {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 6_371_000 * 2 * Math.asin(Math.sqrt(a));
}

export const formatKm = (m: number) => (m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);

/** A gentle curve between two points (a quadratic Bézier bowed to one side), for drawing arcs. */
export function arc(from: LngLat, to: LngLat, bow = 0.18, steps = 48): LngLat[] {
  const [x1, y1] = from;
  const [x2, y2] = to;
  // Control point: the midpoint pushed perpendicular to the segment.
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const cx = mx - (y2 - y1) * bow;
  const cy = my + (x2 - x1) * bow;
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps;
    const u = 1 - t;
    return [u * u * x1 + 2 * u * t * cx + t * t * x2, u * u * y1 + 2 * u * t * cy + t * t * y2];
  });
}

/** Point halfway along an arc (for its label). */
export const midpoint = (line: LngLat[]): LngLat => line[Math.floor(line.length / 2)];
