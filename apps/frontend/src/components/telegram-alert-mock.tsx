import { MOCK_ALERT } from "@/content/page-content";
import { Bell } from "lucide-react";

/** CSS mock of a Telegram property alert — portrait 9:16 frame for hero. */
export function TelegramAlertMock({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`relative mx-auto w-full max-w-[280px] sm:max-w-[300px] ${className}`}
    >
      <div className="absolute -inset-6 rounded-full bg-primary/15 blur-[70px]" />
      <div className="relative aspect-[9/16] overflow-hidden rounded-[2rem] border border-border bg-card p-2.5 shadow-2xl shadow-primary/15">
        <div className="flex h-full flex-col overflow-hidden rounded-[1.5rem] bg-background">
          {/* Status bar */}
          <div className="flex items-center justify-between px-5 pt-3 pb-1">
            <span className="font-mono text-[11px] text-white/70">
              {MOCK_ALERT.time}
            </span>
            <div className="flex items-center gap-1">
              <span className="h-1.5 w-3 rounded-sm bg-white/40" />
              <span className="h-2 w-4 rounded-sm bg-white/50" />
            </div>
          </div>

          {/* Notification card */}
          <div className="flex flex-1 flex-col justify-center px-3 pb-6">
            <div className="rounded-2xl border border-border/80 bg-card p-4 shadow-lg shadow-black/20">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary">
                    <Bell className="size-3.5 text-primary-foreground" />
                  </div>
                  <span className="text-xs font-medium text-white/90">
                    {MOCK_ALERT.appName}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-white/45">
                  {MOCK_ALERT.time}
                </span>
              </div>

              <p className="mt-3 text-sm font-medium text-primary-on-surface">
                🔔 {MOCK_ALERT.title}
              </p>

              <p className="mt-3 text-base font-medium leading-snug text-white">
                🏠 {MOCK_ALERT.property}
              </p>

              <p className="mt-2 font-heading text-xl text-white">
                {MOCK_ALERT.price}
              </p>
              <p className="mt-0.5 text-sm text-white/60">{MOCK_ALERT.details}</p>

              <div className="mt-4 rounded-lg bg-muted/80 px-3 py-2.5">
                <p className="font-mono text-[10px] uppercase tracking-wider text-white/45">
                  {MOCK_ALERT.alertLabel}
                </p>
                <p className="mt-0.5 text-sm text-white/80">
                  {MOCK_ALERT.alertFilter}
                </p>
              </div>

              <div className="mt-4 flex items-center justify-center rounded-lg bg-primary px-3 py-2.5">
                <span className="text-sm font-medium text-primary-foreground">
                  {MOCK_ALERT.cta}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
