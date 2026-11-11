import Link from "next/link";
import { Button } from "@/components/ui/button";

const LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#referee", label: "The referee" },
  { href: "#shield", label: "Kena Shield" },
  { href: "#faq", label: "FAQ" },
];

export function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-background">
      <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-8">
        <Link href="/" className="rounded-sm font-display text-3xl font-bold uppercase leading-none outline-offset-4 focus-visible:outline-2 focus-visible:outline-referee">
          Haggle
        </Link>
        <ul className="ml-4 hidden items-center gap-6 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="rounded-sm text-base text-muted-foreground underline-offset-8 outline-offset-4 transition-colors hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-referee"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <Button
          nativeButton={false}
          render={<Link href="/play" />}
          className="ml-auto h-10 rounded-md bg-live px-4 font-display text-xl font-bold uppercase text-white hover:bg-live/85"
        >
          Start a match
        </Button>
      </nav>
    </header>
  );
}
