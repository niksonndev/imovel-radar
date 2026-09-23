import { MOCK_ALERT } from "@/content/page-content";
import { cn } from "@/lib/utils";

import { LISTING } from "./script";

const WINDOW_LIGHTS = [true, true, false, true, true, true, true, false, true, true, true, false];

export function PropertyCard() {
  return (
    <div data-msg="listing" className="hidden w-[96%] self-start">
      <div className="overflow-hidden rounded-2xl rounded-bl-md bg-[#182533] shadow-lg shadow-black/30">
        <div className="relative h-28 overflow-hidden bg-[#10283a]">
          <div className="absolute inset-0 bg-[linear-gradient(180deg,#24577a_0%,#0c1822_78%)]" />
          <div className="absolute -right-6 -top-8 size-32 rounded-full bg-[#f0d8b0]/20 blur-2xl" />
          <div className="absolute bottom-0 left-1/2 h-[80%] w-[70%] -translate-x-1/2 rounded-t-sm border border-white/20 bg-[#08131c]/80">
            <div className="grid h-full grid-cols-4 grid-rows-3 gap-1.5 p-2">
              {WINDOW_LIGHTS.map((lit, index) => (
                <span
                  key={index}
                  className={cn("rounded-[2px]", lit ? "bg-[#f3e2c4]" : "bg-white/10")}
                />
              ))}
            </div>
          </div>
          <p className="absolute left-2.5 top-2.5 rounded-full bg-black/55 px-2 py-1 text-[11px] font-medium text-white">
            {MOCK_ALERT.title}
          </p>
        </div>

        <div className="px-3.5 py-3">
          <p className="text-sm font-medium leading-snug text-white">🏠 {LISTING.title}</p>
          <p className="mt-1.5 text-lg font-semibold tracking-tight text-white">{LISTING.price}</p>
          <p className="mt-1 text-sm leading-snug text-[#f4f8fb]">
            🛏 {LISTING.rooms} · 📐 {LISTING.area} · 📍 {LISTING.neighbourhood} · {LISTING.kind}
          </p>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-[11px] leading-none text-[#f4f8fb]">{LISTING.counter}</span>
            <span className="text-[11px] leading-none text-[#f4f8fb]">{LISTING.time}</span>
          </div>
        </div>
      </div>

      <div className="mt-1 grid grid-cols-2 overflow-hidden rounded-xl bg-[#24384a]">
        <span className="border-r border-white/10 py-2.5 text-center text-[13px] font-medium text-white">
          Ver anúncio
        </span>
        <span className="py-2.5 text-center text-[13px] font-medium text-white">Acompanhar</span>
      </div>
    </div>
  );
}
