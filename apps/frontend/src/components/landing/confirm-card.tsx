import { ALERT_SUMMARY } from "./script";

export function ConfirmCard({ time }: { time: string }) {
  return (
    <div data-msg="confirm" className="hidden w-[94%] self-start">
      <div className="rounded-2xl rounded-bl-md bg-[#182533] px-3.5 py-3 shadow-sm shadow-black/25">
        <p className="text-sm font-medium text-white">🧾 Confirmação do alerta</p>
        <ul className="mt-2 space-y-1">
          {ALERT_SUMMARY.map((row) => (
            <li key={row.label} className="text-sm leading-snug text-white">
              <span className="font-medium">
                {row.icon} {row.label}:
              </span>{" "}
              {row.value}
            </li>
          ))}
        </ul>
        <p className="mt-2 text-sm leading-snug text-white">Confirme abaixo:</p>
        <div className="mt-1 flex justify-end">
          <span className="text-[11px] leading-none text-[#f4f8fb]">{time}</span>
        </div>
      </div>
    </div>
  );
}
