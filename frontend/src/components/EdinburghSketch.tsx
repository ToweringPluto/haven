import { memo } from "react";

/** Decorative line drawing of the Edinburgh skyline. */
export const EdinburghSketch = memo(function EdinburghSketch({
  className = "",
}: {
  className?: string;
}) {
  return (
    <svg
      className={`edinburgh-sketch ${className}`}
      viewBox="0 0 520 170"
      fill="none"
      aria-hidden="true"
    >
      <path d="M8 151h505M27 151V93l34-21 31 21v58M40 151v-34h17v34M70 151v-39h12v39M92 151V52h82v99M109 78h15v18h-15zM140 78h15v18h-15zM113 113h38M174 151V86l37-25 39 25v65M198 151v-43h25v43M250 151V72h70v79M267 93h14v19h-14zM294 93h14v19h-14zM320 151V103l27-19 28 19v48M375 151V54h71v97M389 75h14v19h-14zM419 75h14v19h-14zM398 151v-33h24v33M446 151V97l28-17 25 17v54" />
      <path d="M92 52l14-15h55l13 15M375 54l12-15h48l11 15M230 75c9-25 17-34 31-43M261 32l8 13M261 32l-12 8M465 78l8-23 9 23" />
      <path className="sketch-dash" d="M12 162c80-11 136 8 217-2 95-12 171 11 279-2" />
    </svg>
  );
});
