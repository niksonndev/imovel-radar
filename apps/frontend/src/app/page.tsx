import { HeroSection } from "@/components/hero-section";
import { FeatureCards } from "@/components/feature-cards";
import { HowItWorks } from "@/components/how-it-works";
import { TelegramPreview } from "@/components/telegram-preview";
import { CTASection } from "@/components/cta-section";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <main className="bg-surface">
        <HeroSection />
        <FeatureCards />
        <HowItWorks />
        <TelegramPreview />
        <CTASection />
      </main>
      <Footer />
    </div>
  );
}
