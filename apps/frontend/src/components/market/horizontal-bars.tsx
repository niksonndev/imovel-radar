"use client";

import { scaleLinear } from "@visx/scale";
import { Bar } from "@visx/shape";
import { defaultStyles, TooltipWithBounds, useTooltip } from "@visx/tooltip";
import { useEffect, useRef, useState } from "react";

export type BarItem = {
  key: string;
  label: string;
  value: number;
  display: string;
};

const tooltipStyles = {
  ...defaultStyles,
  background: "#1a1a1a",
  color: "#fff",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 8,
  fontSize: 12,
};

export function HorizontalBars({
  items,
  label,
  color = "#0077BC",
}: {
  items: BarItem[];
  label: string;
  color?: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(160);
  const { tooltipData, tooltipLeft, tooltipTop, tooltipOpen, showTooltip, hideTooltip } =
    useTooltip<BarItem>();

  useEffect(() => {
    const element = trackRef.current;
    if (!element) return;
    const update = () => setWidth(Math.max(element.clientWidth, 48));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [items]);

  const max = Math.max(...items.map((item) => item.value), 1);
  const scale = scaleLinear<number>({ domain: [0, max], range: [0, width] });

  if (items.length === 0) {
    return <p className="text-sm text-white/50">Sem dados nesta conta.</p>;
  }

  return (
    <div className="relative" onMouseLeave={hideTooltip}>
      <ul aria-label={label} className="flex flex-col gap-2">
        {items.map((item) => (
          <li
            key={item.key}
            className="grid grid-cols-[minmax(5.5rem,8rem)_1fr_auto] items-center gap-3"
            onMouseMove={(event) => {
              const bounds = event.currentTarget.getBoundingClientRect();
              showTooltip({
                tooltipData: item,
                tooltipLeft: event.clientX - bounds.left,
                tooltipTop: event.clientY - bounds.top,
              });
            }}
            onFocus={(event) => {
              const bounds = event.currentTarget.getBoundingClientRect();
              showTooltip({
                tooltipData: item,
                tooltipLeft: bounds.width / 2,
                tooltipTop: 0,
              });
            }}
          >
            <span className="truncate text-sm text-white/80" title={item.label}>
              {item.label}
            </span>
            <div ref={item.key === items[0]?.key ? trackRef : undefined} className="h-4">
              <svg width={width} height={16} role="presentation">
                <Bar
                  x={0}
                  y={2}
                  width={Math.max(scale(item.value), item.value > 0 ? 2 : 0)}
                  height={12}
                  fill={color}
                  rx={4}
                />
              </svg>
            </div>
            <span className="font-mono text-xs text-white/70">{item.display}</span>
          </li>
        ))}
      </ul>
      {tooltipOpen && tooltipData ? (
        <TooltipWithBounds top={tooltipTop} left={tooltipLeft} style={tooltipStyles}>
          {tooltipData.label}: {tooltipData.display}
        </TooltipWithBounds>
      ) : null}
    </div>
  );
}
