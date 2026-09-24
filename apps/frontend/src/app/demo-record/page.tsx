import type { Metadata } from "next";

import { TelegramDemo } from "@/components/landing/TelegramDemo";

export const metadata: Metadata = {
  title: "Demo record",
  robots: { index: false, follow: false },
};

/**
 * Same phone chrome as the landing hero (400×34rem), framed for Playwright
 * recording — no site layout changes. See `pnpm record:demo`.
 */
export default function DemoRecordPage() {
  return (
    <main data-demo-record className="m-0 inline-block bg-[#0e1621] p-0">
      <TelegramDemo
        autoPlay
        playOnce
        hideGlow
        className="m-0 max-w-100"
        // Lock desktop hero height so a tight recording viewport doesn't shrink the shell.
        shellClassName="h-136 min-h-136"
      />
    </main>
  );
}
