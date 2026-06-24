import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the current directory to python path so we can import app
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

load_dotenv()

from app.db import SessionLocal
from app.agents.roi_validator import validate_roi

async def main():
    db = SessionLocal()
    strategy_id = "7d4421d4-8e6e-4ba3-877e-7492d04a495d"
    try:
        print(f"Calling validate_roi for strategy {strategy_id}...")
        result = await validate_roi(
            db,
            strategy_id,
            investment_usd=250000,
            expected_revenue_usd=1500000,
            timeframe_months=12,
            market_segment="Healthcare AI, mid-market",
            notes=""
        )
        print("RESULT:")
        print(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
