import {
  FEATURE_1_TITLE,
  FEATURE_1_DESC,
  FEATURE_2_TITLE,
  FEATURE_2_DESC,
  FEATURE_3_TITLE,
  FEATURE_3_DESC,
  FEATURES_SECTION_HEADING,
} from "@/content/page-content";
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
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10">
        <h2 className="text-center font-heading text-3xl leading-tight tracking-tight text-white sm:text-4xl">
          {FEATURES_SECTION_HEADING}
        </h2>
        <div className="grid w-full gap-6 sm:grid-cols-3 sm:gap-8">
          {features.map((feature) => (
            <article
              key={feature.title}
              className="group reveal-on-scroll flex flex-col gap-4 rounded-lg border bg-card p-6 text-card-foreground shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/10"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 transition-colors duration-300 group-hover:bg-primary/20">
                <feature.icon className="size-5 text-primary" />
              </div>
              <h3 className="font-heading text-lg text-card-foreground">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
