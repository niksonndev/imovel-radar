"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Radar } from "lucide-react";

import { cn } from "@/lib/utils";

import { ChatBubble } from "./chat-bubble";
import { ConfirmCard } from "./confirm-card";
import { PropertyCard } from "./property-card";
import { DEMO_STEPS, type DemoStep } from "./script";
import { TypingIndicator } from "./typing-indicator";

gsap.registerPlugin(useGSAP);

const PAYOFF_HOLD = 2.7;
const TYPING_HOLD = 0.65;

type BuildArgs = {
  root: HTMLElement;
  viewport: HTMLElement;
  stack: HTMLElement;
};

function scrollTarget(stack: HTMLElement, viewport: HTMLElement) {
  const overflow = stack.scrollHeight - viewport.clientHeight;
  return overflow > 0 ? -overflow : 0;
}

function buildConversation(tl: gsap.core.Timeline, { root, viewport, stack }: BuildArgs) {
  const typing = root.querySelector<HTMLElement>("[data-typing]");
  const scrollY = () => scrollTarget(stack, viewport);

  const reveal = (step: DemoStep, at: gsap.Position) => {
    const el = root.querySelector<HTMLElement>(`[data-msg="${step.id}"]`);
    if (!el) return;
    const duration = step.kind === "listing" ? 0.55 : 0.42;
    tl.call(() => el.classList.remove("hidden"), [], at);
    tl.to(el, { autoAlpha: 1, y: 0, duration }, "<");
    tl.to(stack, { y: scrollY, duration: 0.48, ease: "power3.out" }, "<");
  };

  DEMO_STEPS.forEach((step, index) => {
    const gap = index === 0 ? 0.4 : step.role === "user" ? 0.42 : 0.18;
    tl.addLabel(step.id, `+=${gap}`);

    const withTyping = step.role === "bot" && !("typing" in step && step.typing === false);
    if (withTyping && typing) {
      tl.call(() => typing.classList.remove("hidden"), [], step.id);
      tl.to(typing, { autoAlpha: 1, y: 0, duration: 0.26 }, "<");
      tl.to(stack, { y: scrollY, duration: 0.4, ease: "power3.out" }, "<");

      const revealAt = `${step.id}+=${TYPING_HOLD}`;
      tl.call(() => typing.classList.add("hidden"), [], revealAt);
      tl.set(typing, { autoAlpha: 0, y: 8 }, "<");
      reveal(step, "<");
    } else {
      reveal(step, step.id);
    }

    if ("pauseAfter" in step && step.pauseAfter) {
      tl.to(stack, { y: scrollY, duration: step.pauseAfter, ease: "none" });
    }
  });

  tl.addLabel("payoff");
  tl.to(stack, { y: scrollY, duration: PAYOFF_HOLD, ease: "none" }, "payoff");
  tl.addLabel("reset");
  tl.to(stack, { autoAlpha: 0, duration: 0.4, ease: "power1.in" }, "reset");
}

function showPayoff(root: HTMLElement, stack: HTMLElement, viewport: HTMLElement) {
  root.querySelectorAll<HTMLElement>("[data-msg]").forEach((el) => {
    const keep = el.dataset.msg === "confirm" || el.dataset.msg === "listing";
    el.classList.toggle("hidden", !keep);
    gsap.set(el, { autoAlpha: keep ? 1 : 0, y: 0 });
  });
  const typing = root.querySelector<HTMLElement>("[data-typing]");
  typing?.classList.add("hidden");
  if (typing) gsap.set(typing, { autoAlpha: 0, y: 0 });
  const overflow = stack.scrollHeight - viewport.clientHeight;
  gsap.set(stack, { autoAlpha: 1, y: overflow > 0 ? -overflow : 0 });
}

export function TelegramDemo({ className = "" }: { className?: string }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const stackRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const root = rootRef.current;
      const viewport = viewportRef.current;
      const stack = stackRef.current;
      if (!root || !viewport || !stack) return;

      const mm = gsap.matchMedia();
      mm.add(
        {
          reduceMotion: "(prefers-reduced-motion: reduce)",
          allowMotion: "(prefers-reduced-motion: no-preference)",
        },
        (context) => {
          const messages = gsap.utils.toArray<HTMLElement>("[data-msg]", root);
          const typing = root.querySelector<HTMLElement>("[data-typing]");

          if (context.conditions?.reduceMotion) {
            showPayoff(root, stack, viewport);
            return;
          }

          messages.forEach((el) => el.classList.add("hidden"));
          typing?.classList.add("hidden");
          gsap.set(messages, { autoAlpha: 0, y: 8 });
          if (typing) gsap.set(typing, { autoAlpha: 0, y: 8 });
          gsap.set(stack, { autoAlpha: 1, y: 0 });

          const dots = gsap.utils.toArray<HTMLElement>("[data-dot]", root);
          const dotsTween = gsap.to(dots, {
            autoAlpha: 0.35,
            duration: 0.42,
            ease: "power1.inOut",
            stagger: { each: 0.14, yoyo: true, repeat: -1 },
          });
          dotsTween.pause();

          let inView = false;
          const tl = gsap.timeline({
            paused: true,
            defaults: { duration: 0.4, ease: "power2.out" },
            onComplete: () => {
              if (!root.isConnected) return;
              messages.forEach((el) => el.classList.add("hidden"));
              typing?.classList.add("hidden");
              gsap.set(messages, { autoAlpha: 0, y: 8 });
              if (typing) gsap.set(typing, { autoAlpha: 0, y: 8 });
              gsap.set(stack, { autoAlpha: 1, y: 0 });
              tl.invalidate();
              tl.restart();
              if (!inView) tl.pause();
            },
          });

          buildConversation(tl, { root, viewport, stack });

          const observer = new IntersectionObserver(
            ([entry]) => {
              inView = Boolean(entry?.isIntersecting);
              if (inView) {
                tl.play();
                dotsTween.play();
              } else {
                tl.pause();
                dotsTween.pause();
              }
            },
            { threshold: 0.2 },
          );
          observer.observe(root);

          return () => observer.disconnect();
        },
        root,
      );

      return () => mm.revert();
    },
    { scope: rootRef },
  );

  return (
    <div className={cn("relative mx-auto w-full max-w-[400px]", className)}>
      <p className="sr-only">
        Demonstração do bot no Telegram: o alerta Novo apê, para alugar um apartamento em Antares
        e Serraria entre R$ 2.000 e R$ 2.500 com 3 quartos ou mais, encontra um apartamento em
        Antares por R$ 2.300.
      </p>

      <div ref={rootRef} aria-hidden="true" className="relative">
        <div className="pointer-events-none absolute -inset-8 -z-10 rounded-full bg-primary/20 blur-3xl" />
        <div className="flex h-[min(34rem,calc(100svh-11.5rem))] min-h-[28rem] flex-col overflow-hidden rounded-[28px] border border-white/10 bg-[#0e1621] shadow-[0_24px_80px_-24px_rgba(0,119,188,0.55)]">
          <header className="flex shrink-0 items-center gap-3 border-b border-white/10 bg-[#17212b] px-4 py-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-[#0077BC]">
              <Radar className="size-5 text-white" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">Imóvel Radar</p>
              <p className="text-xs text-[#d7e6f2]">bot</p>
            </div>
          </header>

          <div
            ref={viewportRef}
            className="relative min-h-0 flex-1 overflow-hidden bg-[#0e1621] bg-[radial-gradient(circle_at_12%_0%,rgba(0,119,188,0.18),transparent_42%),radial-gradient(circle_at_100%_100%,rgba(0,152,102,0.1),transparent_38%)]"
          >
            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-12 bg-gradient-to-b from-[#0e1621] to-transparent" />
            <div ref={stackRef} className="flex flex-col gap-2 px-3 py-4 will-change-transform">
              {DEMO_STEPS.map((step) => {
                if (step.kind === "confirm") {
                  return <ConfirmCard key={step.id} time={step.time} />;
                }
                if (step.kind === "listing") {
                  return <PropertyCard key={step.id} />;
                }
                return (
                  <ChatBubble
                    key={step.id}
                    id={step.id}
                    role={step.role}
                    time={step.time}
                    title={step.title}
                    body={step.body}
                  />
                );
              })}
              <TypingIndicator />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
