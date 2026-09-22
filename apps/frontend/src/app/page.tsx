import { HeroSection } from "@/components/hero-section";
import { HowItWorks } from "@/components/how-it-works";
import { ExampleSearches } from "@/components/example-searches";
import { NeighborhoodsMarquee } from "@/components/neighborhoods-marquee";
import { PricingSection } from "@/components/pricing-section";
import { FaqSection } from "@/components/faq-section";
import { CTASection } from "@/components/cta-section";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <main className="bg-surface">
        <HeroSection />
        <HowItWorks />
        <ExampleSearches />
        <NeighborhoodsMarquee />
        <PricingSection />
        <FaqSection />
        <CTASection />
      </main>
      <Footer />
    </div>
  );
}
