import { CheckCheck } from "lucide-react";

import { cn } from "@/lib/utils";

import type { DemoRole } from "./script";

type ChatBubbleProps = {
  id: string;
  role: DemoRole;
  time: string;
  title?: string;
  body: string;
};

export function ChatBubble({ id, role, time, title, body }: ChatBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      data-msg={id}
      className={cn("hidden max-w-[88%]", isUser ? "self-end" : "self-start")}
    >
      <div
        className={cn(
          "rounded-2xl px-3 py-2 shadow-sm shadow-black/25",
          isUser ? "rounded-br-md bg-[#0077BC]" : "rounded-bl-md bg-[#182533]",
        )}
      >
        {title ? (
          <p className="text-sm font-medium leading-snug text-white">{title}</p>
        ) : null}
        <p className={cn("text-sm leading-snug text-white", title && "mt-1")}>
          {body}
        </p>
        <div className="mt-1 flex items-center justify-end gap-1">
          <span className="text-[11px] leading-none text-[#f4f8fb]">{time}</span>
          {isUser ? (
            <CheckCheck className="size-3.5 text-[#f4f8fb]" strokeWidth={2.25} aria-hidden="true" />
          ) : null}
        </div>
      </div>
    </div>
  );
}
