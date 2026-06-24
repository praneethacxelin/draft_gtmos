import httpx

base_url = "http://localhost:8080"

def test():
    # 1. Get strategies
    r = httpx.get(f"{base_url}/api/strategies")
    strategies = r.json()
    
    for strat in strategies:
        strat_id = strat["id"]
        product_name = strat.get("product_name") or "<unnamed>"
        print(f"\n--- Strategy: {strat_id} ({product_name}) ---")
        
        # Test GET strategy details
        r_det = httpx.get(f"{base_url}/api/strategies/{strat_id}")
        print("  GET strategy status:", r_det.status_code)
        print("  Response:", r_det.text[:200])

if __name__ == "__main__":
    test()
