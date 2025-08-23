import argparse, asyncio, yaml, os
from dotenv import load_dotenv
from src.agents.trading_agent import TradingAgent

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    return ap.parse_args()

async def amain(cfg):
    agent = TradingAgent(cfg)
    await agent.run()

def main():
    load_dotenv()
    args = parse_args()
    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)
    asyncio.run(amain(cfg))

if __name__ == "__main__":
    main()
