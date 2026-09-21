import { HeroSection } from "@/components/hero-section";
import { NeighborhoodsMarquee } from "@/components/neighborhoods-marquee";
import { SocialProof } from "@/components/social-proof";
import { FeatureCards } from "@/components/feature-cards";
import { HowItWorks } from "@/components/how-it-works";
import { TelegramPreview } from "@/components/telegram-preview";
import { PricingSection } from "@/components/pricing-section";
import { CTASection } from "@/components/cta-section";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <main className="bg-surface">
        <HeroSection />
        <NeighborhoodsMarquee />
        <SocialProof />
        <FeatureCards />
        <HowItWorks />
        <TelegramPreview />
        <PricingSection />
        <CTASection />
      </main>
      <Footer />
    </div>
  );
}
