from urllib.parse import urlparse
import re

TIER_1_DOMAINS = [
    "statista.com", "mckinsey.com", "deloitte.com", "pwc.com", 
    "bcg.com", "bain.com", "idc.com", "gartner.com"
]

TIER_2_KEYWORDS = [
    "investor", "press-release", "newsroom", "about-us", "pr"
]

TIER_3_KEYWORDS = [
    "news", "tech", "crunch", "wire", "journal", "biz", "industry", "media", "post", "times"
]

def get_source_quality_score(url: str, company_domain: str = "") -> int:
    """
    Returns a score from 40 to 100 based on the source quality tiers:
    Tier 1: 100 (Statista, McKinsey, etc.)
    Tier 2: 80 (Company websites, PR, investor relations)
    Tier 3: 60 (Industry publications)
    Tier 4: 40 (Unknown websites)
    """
    if not url:
        return 40
        
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    
    # Tier 1
    if any(domain == td or domain.endswith("." + td) for td in TIER_1_DOMAINS):
        return 100
        
    # Tier 2: Company website itself or contains PR/investor keywords
    company_domain = company_domain.lower().replace("www.", "") if company_domain else ""
    if company_domain and (domain == company_domain or domain.endswith("." + company_domain)):
        return 80
        
    if any(kw in path or kw in domain for kw in TIER_2_KEYWORDS):
        return 80
        
    # Tier 3: Industry publications (heuristic)
    if any(kw in domain for kw in TIER_3_KEYWORDS):
        return 60
        
    # Tier 4: Unknown
    return 40

def calculate_confidence_score(source_quality: int, keyword_match_strength: float = 1.0, is_recent: bool = True) -> int:
    """
    Calculate a confidence score (0-100) based on source quality, keyword match, and recency.
    """
    # Source quality contributes 60%
    base = source_quality * 0.6
    
    # Keyword match contributes 30%
    kw_score = (keyword_match_strength * 100) * 0.3
    
    # Recency contributes 10%
    recency_score = 10 if is_recent else 0
    
    total = int(base + kw_score + recency_score)
    return min(100, max(0, total))
