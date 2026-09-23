"use client";

import { sendGTMEvent } from "@next/third-parties/google";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import type { VariantProps } from "class-variance-authority";
import type { ComponentPropsWithoutRef, ReactNode } from "react";

type ButtonVariant = VariantProps<typeof buttonVariants>["variant"];
type ButtonSize = VariantProps<typeof buttonVariants>["size"];

type TrackedCtaProps = {
  href: string;
  ctaId: string;
  children: ReactNode;
  className?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  showIcon?: boolean;
} & Omit<ComponentPropsWithoutRef<"a">, "href" | "children" | "className">;

/**
 * Primary CTA to the Telegram bot. Pushes `cta_click` to GTM dataLayer.
 */
export function TrackedCta({
  href,
  ctaId,
  children,
  className,
  variant = "default",
  size = "cta",
  showIcon = true,
  onClick,
  ...rest
}: TrackedCtaProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      data-cta={ctaId}
      className={cn(buttonVariants({ variant, size }), className)}
      onClick={(event) => {
        sendGTMEvent({
          event: "cta_click",
          cta_id: ctaId,
          cta_destination: "telegram_bot",
        });
        onClick?.(event);
      }}
      {...rest}
    >
      {showIcon ? <Send className="size-4" data-icon="inline-start" /> : null}
      {children}
    </a>
  );
}
