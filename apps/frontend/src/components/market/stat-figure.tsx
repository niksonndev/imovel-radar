"use client";

import NumberFlow from "@number-flow/react";

export function StatFigure({
  value,
  currency = false,
}: {
  value: number | null;
  currency?: boolean;
}) {
  if (value == null) {
    return <span className="font-heading text-3xl text-white">—</span>;
  }
  return (
    <NumberFlow
      value={value}
      locales="pt-BR"
      format={
        currency
          ? { style: "currency", currency: "BRL", maximumFractionDigits: 0 }
          : { maximumFractionDigits: 0 }
      }
      className="font-heading text-3xl text-white"
    />
  );
}
