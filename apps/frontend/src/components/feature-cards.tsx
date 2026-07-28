import {
  FEATURE_1_TITLE,
  FEATURE_1_DESC,
  FEATURE_2_TITLE,
  FEATURE_2_DESC,
  FEATURE_3_TITLE,
  FEATURE_3_DESC,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Search, Filter, Bell } from "lucide-react";

const features = [
  {
    icon: Search,
    title: FEATURE_1_TITLE,
    description: FEATURE_1_DESC,
  },
  {
    icon: Filter,
    title: FEATURE_2_TITLE,
    description: FEATURE_2_DESC,
  },
  {
    icon: Bell,
    title: FEATURE_3_TITLE,
    description: FEATURE_3_DESC,
  },
];

export function FeatureCards() {
  return (
    <section className="px-4 py-16 sm:py-20">
      <div className="mx-auto grid w-full max-w-5xl gap-6 sm:grid-cols-3 sm:gap-8">
        {features.map((feature) => (
          <article
            key={feature.title}
            className="flex flex-col gap-4 rounded-lg border bg-card p-6 text-card-foreground shadow-sm"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10">
              <feature.icon className="size-5 text-primary" />
            </div>
            <h3 className="font-heading text-lg text-card-foreground">
              {feature.title}
            </h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {feature.description}
            </p>
            <a
              href={TELEGRAM_BOT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                buttonVariants({ variant: "link" }),
                "mt-auto self-start px-0"
              )}
            >
              Começar agora
            </a>
          </article>
        ))}
      </div>
    </section>
  );
}