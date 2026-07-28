import {
  FOOTER_LEGAL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ExternalLink } from "lucide-react";

export function Footer() {
  return (
    <footer className="flex flex-col items-center justify-center gap-4 bg-surface px-4 py-12">
      <a
        href={TELEGRAM_BOT_URL}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          buttonVariants({ variant: "ghost" }),
          "gap-2 text-white/70 hover:text-white hover:bg-white/10"
        )}
      >
        <ExternalLink className="size-4" />
        Telegram
      </a>
      <p className="font-mono text-xs tracking-wider text-white/40">
        {FOOTER_LEGAL}
      </p>
    </footer>
  );
}