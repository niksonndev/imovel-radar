"use client";

import { sendGTMEvent } from "@next/third-parties/google";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ArrowRight } from "lucide-react";
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
 * Primary assistant CTA. Pushes `cta_click` to GTM dataLayer.
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
      target={href.startsWith("/") ? undefined : "_blank"}
      rel={href.startsWith("/") ? undefined : "noopener noreferrer"}
      data-cta={ctaId}
      className={cn(buttonVariants({ variant, size }), className)}
      onClick={(event) => {
        sendGTMEvent({
          event: "cta_click",
          cta_id: ctaId,
          cta_destination: "assistant_updates",
        });
        onClick?.(event);
      }}
      {...rest}
    >
      {showIcon ? <ArrowRight className="size-4 transition-transform group-hover/button:translate-x-0.5" data-icon="inline-end" /> : null}
      {children}
    </a>
  );
}
