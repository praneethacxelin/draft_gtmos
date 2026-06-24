import sys
import os
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from app.db import SessionLocal, User
from app.routes.strategies import roi_validate, RoiValidateRequest

async def main():
    db = SessionLocal()
    # Let's find user
    user = db.query(User).first()
    if not user:
        print("No user found in DB!")
        return
        
    strategy_id = "e4437919-f15b-40ea-8440-f4dcfd2c6f89"
    body = RoiValidateRequest(
        investment_usd=10000,
        expected_revenue_usd=50000,
        timeframe_months=12,
        market_segment="SaaS",
        notes=""
    )
    
    print("Testing roi_validate internally...")
    try:
        res = await roi_validate(strategy_id=strategy_id, body=body, db=db, user=user)
        print("Result:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()
        
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
