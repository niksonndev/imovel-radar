import { MOCK_ALERT } from "@/content/page-content";
import { Bell } from "lucide-react";

/** CSS mock of a Telegram property alert. Short frame on small screens, 9:16 from lg. */
export function TelegramAlertMock({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`relative mx-auto w-full max-w-65 lg:max-w-75 ${className}`}
    >
      <div className="absolute -inset-6 rounded-full bg-primary/15 blur-[70px]" />
      <div className="relative aspect-4/5 overflow-hidden rounded-4xl border border-border bg-card p-2.5 shadow-2xl shadow-primary/15 lg:aspect-9/16">
        <div className="flex h-full flex-col overflow-hidden rounded-3xl bg-background">
          {/* Status bar */}
          <div className="hidden items-center justify-between px-5 pt-3 pb-1 lg:flex">
            <span className="font-mono text-[11px] text-white/70">
              {MOCK_ALERT.time}
            </span>
            <div className="flex items-center gap-1">
              <span className="h-1.5 w-3 rounded-sm bg-white/40" />
              <span className="h-2 w-4 rounded-sm bg-white/50" />
            </div>
          </div>

          {/* Notification card */}
          <div className="flex flex-1 flex-col justify-center px-2.5 py-2 lg:px-3 lg:pt-0 lg:pb-6">
            <div className="rounded-2xl border border-border/80 bg-card p-2.5 shadow-lg shadow-black/20 lg:p-4">
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

              <p className="mt-1.5 text-sm font-medium text-primary-on-surface lg:mt-3">
                {MOCK_ALERT.title}
              </p>

              <p className="mt-1.5 text-sm font-medium leading-tight text-white lg:mt-3 lg:text-base lg:leading-snug">
                🏠 {MOCK_ALERT.property}
              </p>

              <p className="mt-1 font-heading text-lg text-white lg:mt-2 lg:text-xl">
                {MOCK_ALERT.price}
              </p>
              <p className="mt-0.5 text-sm text-white/60">{MOCK_ALERT.details}</p>

              <div className="mt-2 rounded-lg bg-muted/80 px-2.5 py-1.5 lg:mt-4 lg:px-3 lg:py-2.5">
                <p className="font-mono text-[10px] uppercase tracking-wider text-white/45">
                  {MOCK_ALERT.alertLabel}
                </p>
                <p className="mt-0.5 text-sm text-white/80">
                  {MOCK_ALERT.alertFilter}
                </p>
              </div>

              <div className="mt-2 flex items-center justify-center rounded-lg bg-primary px-3 py-1.5 lg:mt-4 lg:py-2.5">
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
