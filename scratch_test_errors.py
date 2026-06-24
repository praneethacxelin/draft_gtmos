import httpx

base_url = "http://localhost:8080"
strat_id = "4a40b8e7-f45f-47fb-abf9-2b79a0d21469"

endpoints = [
    ("GET", f"/api/strategies/{strat_id}"),
    ("GET", f"/api/strategies/{strat_id}/campaign-plan"),
    ("POST", f"/api/strategies/{strat_id}/roi/validate"),
    ("POST", f"/api/strategies/{strat_id}/discovery/document"),
    ("POST", f"/api/strategies/{strat_id}/experiments")
]

for method, path in endpoints:
    url = f"{base_url}{path}"
    print(f"\n--- Testing {method} {path} ---")
    try:
        if method == "GET":
            r = httpx.get(url)
        else:
            if "roi/validate" in path:
                r = httpx.post(url, json={"investment_usd": 10000, "expected_revenue_usd": 50000, "timeframe_months": 12})
            elif "experiments" in path:
                r = httpx.post(url, json={"n": 3, "leads_per_experiment": 10})
            else:
                r = httpx.post(url)
        print("Status:", r.status_code)
        print("Response:", r.text[:300])
    except Exception as e:
        print("Exception:", e)
