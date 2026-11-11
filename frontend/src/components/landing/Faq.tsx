import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

const QUESTIONS = [
  {
    q: "Does real money move?",
    a: "Not yet. Payments run on PayPal's sandbox, which uses test accounts only. The hold, the capture, the void and the refund all work for real against the sandbox, but nobody is charged.",
  },
  {
    q: "Do I need an API key to try it?",
    a: "No. By default, simple rule-based agents play the match, so it runs with no key. Switch on \"Let Claude play both sides\" and Claude proposes the moves and writes the banter instead.",
  },
  {
    q: "What stops an agent overspending?",
    a: "The budget cap is enforced in code at every price and again at every payment call, and the buyer must approve before any money moves. The agents never touch the payment system.",
  },
  {
    q: "Who can see the budget and the floor?",
    a: "Nobody in the room. Both limits are enforced in code and hidden from spectators, and each agent only sees its own limit, never the other side's.",
  },
  {
    q: "What are lucky numbers?",
    a: "A house rule for the match. In the Malaysian-Chinese setting, 8 is lucky and 4 is avoided, so the referee nudges prices toward 8s and away from 4s. The neutral setting turns this off.",
  },
];

export function Faq() {
  return (
    <Accordion className="border-b border-line-strong">
      {QUESTIONS.map((item) => (
        <AccordionItem key={item.q} value={item.q} className="border-t border-line-strong">
          <AccordionTrigger className="py-5 font-display text-2xl font-bold uppercase hover:no-underline sm:text-3xl">{item.q}</AccordionTrigger>
          <AccordionContent className="max-w-prose text-lg text-muted-foreground">{item.a}</AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
