/** Marks pre-processed demo output so it is never mistaken for a live result. */
export function SampleLabel({ children = "Sample result" }: { children?: string }) {
  return <span className="sample-label">{children}</span>;
}
