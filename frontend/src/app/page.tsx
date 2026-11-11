import type { Metadata } from "next";
import { Nav } from "@/components/landing/Nav";
import { FaceRules, FinalCta, Footer, Hero, HowItWorks, Questions, Roles, Shield, Ticker } from "@/components/landing/Sections";

export const metadata: Metadata = {
  title: "Haggle: two AI agents, one price, live",
  description:
    "Two AI agents haggle over a price while you watch. Code decides every number, and a payment shield holds the money until delivery.",
};

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Ticker />
        <HowItWorks />
        <Roles />
        <FaceRules />
        <Shield />
        <Questions />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}
