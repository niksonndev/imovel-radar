import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import {
  TELEGRAM_PREVIEW_HEADLINE,
  TELEGRAM_PREVIEW_SUBHEADLINE,
  MOCK_ALERTS,
  SECTION_CTA_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { SITE_NAME } from "@/lib/site";

export function TelegramPreview() {
  return (
    <section className="px-4 py-20 sm:py-28">
      <div className="mx-auto grid w-full max-w-5xl items-center gap-12 md:grid-cols-2">
        {/* Texto */}
        <div className="reveal-on-scroll flex flex-col items-start gap-5">
          <h2 className="font-heading text-3xl leading-tight tracking-tight text-white sm:text-4xl">
            {TELEGRAM_PREVIEW_HEADLINE}
          </h2>
          <p className="max-w-md text-lg leading-relaxed text-white/70">
            {TELEGRAM_PREVIEW_SUBHEADLINE}
          </p>
          <a
            href={TELEGRAM_BOT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              buttonVariants({ variant: "default", size: "lg" }),
              "btn-shine mt-2 h-11 px-6 text-base"
            )}
          >
            <Send className="size-4" data-icon="inline-start" />
            {SECTION_CTA_LABEL}
          </a>
        </div>

        {/* Mockup do Telegram (ilustrativo) */}
        <div
          aria-hidden="true"
          className="reveal-on-scroll relative mx-auto w-full max-w-xs"
        >
          <div className="absolute -inset-8 rounded-full bg-primary/10 blur-[80px]" />
          <div className="relative rounded-[2rem] border border-border bg-card p-3 shadow-2xl shadow-primary/10">
            <div className="overflow-hidden rounded-[1.6rem] bg-background">
              {/* Cabeçalho da conversa */}
              <div className="flex items-center gap-3 border-b border-border bg-card px-4 py-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary">
                  <Send className="size-4 text-primary-foreground" />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-white">
                    {SITE_NAME} Bot
                  </span>
                  <span className="flex items-center gap-1.5 text-xs text-secondary">
                    <span className="size-1.5 rounded-full bg-secondary" />
                    online
                  </span>
                </div>
              </div>

              {/* Mensagens */}
              <div className="flex flex-col gap-2 px-4 py-4">
                {MOCK_ALERTS.map((alert) => (
                  <div
                    key={alert.title}
                    className="max-w-[85%] self-start rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2.5"
                  >
                    <p className="text-sm font-medium text-white">
                      {alert.title}
                    </p>
                    <p className="mt-0.5 text-xs text-white/60">{alert.detail}</p>
                    <p className="mt-1 text-right font-mono text-[10px] text-white/60">
                      {alert.time}
                    </p>
                  </div>
                ))}

                {/* Indicador "digitando…" */}
                <div className="flex w-fit items-center gap-1.5 self-start rounded-2xl rounded-bl-sm bg-muted px-3.5 py-3">
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className="size-1.5 animate-bounce rounded-full bg-white/50"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}