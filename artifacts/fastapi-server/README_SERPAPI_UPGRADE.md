# SERP API Upgrade

This document outlines the changes made during the SERP API upgrade.

## 1. Hybrid Retrieval Approach

We have introduced a `hybrid_serpapi_search` in `app/services/clients.py` which concurrently fetches results from both the standard `google` engine and the `google_news` engine. It then merges and deduplicates the results. This approach ensures we capture both general knowledge and the most recent news updates for competitors and general market research.

## 2. Source-Quality and Confidence Scoring

A new module for scoring (`app/agents/scoring_utils.py`) has been implemented to provide:
*   **Source Quality Score (40-100)**: Tiers domains based on authority. Tier 1 (100) includes top analyst firms like Statista, McKinsey, Gartner, etc. Tier 2 (80) covers company websites and press releases. Tier 3 (60) covers industry publications. Tier 4 (40) is for unknown websites.
*   **Confidence Score (0-100)**: Combines the source quality score, keyword match strength, and recency to provide a robust confidence metric for each signal or market sizing data point.

## 3. Market Research & Sizing

The `run_market_sizing` pipeline now utilizes a 24-month date filter (`tbs="qdr:m24"`) and prefers high-quality sources like Statista and Grand View Research. The LLM prompt enforces a strict JSON output structure that includes `confidence_score` and references the sources used.

## 4. Company Research

The `run_competitors` pipeline was updated to use the `hybrid_serpapi_search` with a 90-day date filter (`tbs="qdr:m3"`) when gathering recent news about competitors.

## 5. Signal Generation

The `run_signals` pipeline was significantly upgraded:
*   Uses a 30-day date filter (`tbs="qdr:m"`).
*   Implements multi-query retrieval across 6 categories: Hiring, Funding, Product Launch, Partnership, Expansion, Technology Adoption.
*   Uses `hybrid_serpapi_search` to maximize coverage.
*   **LLM Validation**: Adds an LLM call to process all aggregated search snippets, which validates the extracted signals, removes duplicates/stale signals, and normalizes the output to include `confidence_score` and `source_quality_score`.

## API Quota Management

Due to the multi-query approach for signals (6 categories × 2 engines), API usage will increase. The system manages this by allocating a `per_query_budget` per category based on the overall `signals_per_account` limit.
