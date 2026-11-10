import { StartForm } from "@/components/StartForm";

export default function Home() {
  return (
    <main className="mx-auto grid min-h-dvh max-w-6xl gap-10 px-4 py-10 sm:px-8 lg:grid-cols-[1fr_1.1fr] lg:gap-16 lg:py-16">
      <div>
        <h1 className="font-display text-7xl font-bold uppercase leading-[0.9] sm:text-8xl">Haggle</h1>
        <p className="mt-6 max-w-md text-xl leading-relaxed text-balance">
          Two AI agents fight over a price, live. Code decides the numbers. The agents only do the talking.
        </p>
      </div>
      <StartForm />
    </main>
  );
}
