import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  secondary?: boolean;
}

export function Button({ secondary = false, className, type = "button", ...rest }: ButtonProps) {
  const classes = ["button", secondary && "button-secondary", className].filter(Boolean).join(" ");
  return <button type={type} className={classes} {...rest} />;
}
