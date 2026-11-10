"""Watch one negotiation in the terminal.

uv run python -m scripts.run_negotiation [--llm]
"""

import argparse
import asyncio

from app.config import settings
from app.negotiation.agents import Agent, LLMAgent, RuleAgent
from app.negotiation.graph import NegotiationConfig, run_negotiation


async def main(use_llm: bool) -> None:
    config = NegotiationConfig(
        "Vintage Yamaha guitar", budget_cap=950, seller_floor=700, opening_ask=1288
    )
    if use_llm and not settings.anthropic_api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env")
    agent: Agent = (
        LLMAgent(settings.anthropic_api_key, settings.llm_model) if use_llm else RuleAgent()
    )
    async for e in run_negotiation(config, agent, agent):
        print(
            f"{e.turn:>2} {e.side:<6} {e.action:<6} price={e.price} gap={e.gap} "
            f"face={e.buyer_face}/{e.seller_face} | {e.message}"
        )
        if e.final_price is not None or e.status != "ongoing":
            print(f"=> {e.status} final_price={e.final_price}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true")
    asyncio.run(main(parser.parse_args().llm))
