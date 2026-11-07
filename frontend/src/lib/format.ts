const gbp = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

/** Formats a whole-pound amount, e.g. 1095 → "£1,095". */
export const formatGBP = (amount: number) => gbp.format(amount);
