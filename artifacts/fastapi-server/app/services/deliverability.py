"""Deliverability service for cold email sequences.

Analyzes subject lines, email copy, and domain settings to compute a deliverability score and recommendations.
"""
from typing import Optional, List, Dict, Any
import re

SPAM_WORDS = {
    "free", "buy now", "guarantee", "urgent", "make money", "winner",
    "cash", "credit", "earn", "risk free", "double your", "limited time",
    "click here", "subscribe", "exclusive offer", "act now", "apply now",
    "cheap", "save money", "unsecured debt", "special promotion", "best price"
}

def analyze_email_content(subject: str, body: str) -> Dict[str, Any]:
    """Analyze subject and body for spam signals and layout issues."""
    score = 100.0
    warnings = []
    recommendations = []

    combined_text = (subject + " " + body).lower()
    
    # 1. Check for spam trigger words
    found_spam = []
    for word in SPAM_WORDS:
        # Use regex to find whole words/phrases
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, combined_text):
            found_spam.append(word)
            score -= 10.0
            
    if found_spam:
        warnings.append(f"Spam trigger words detected: {', '.join(found_spam)}")
        recommendations.append("Remove high-risk sales/spam words to bypass automated spam filters.")

    # 2. Check email length
    word_count = len(body.split())
    if word_count > 0 and word_count < 30:
        score -= 5.0
        warnings.append("Body copy is extremely short (< 30 words).")
        recommendations.append("Add more context or value to ensure spam filters do not flag it as thin content.")
    elif word_count > 250:
        score -= 5.0
        warnings.append("Body copy is quite long (> 250 words).")
        recommendations.append("Keep cold emails concise (ideal length is 50-150 words) to maximize engagement.")

    # 3. Check for links
    link_count = len(re.findall(r"https?://", body))
    if link_count > 1:
        score -= (link_count - 1) * 10.0
        warnings.append(f"High link count ({link_count} links detected).")
        recommendations.append("Minimize links in the first outreach email. Keep it to 1 link max, ideally none.")

    # 4. Check for capital letters
    caps_ratio = sum(1 for c in combined_text if c.isupper()) / max(1, len(combined_text))
    if caps_ratio > 0.25:
        score -= 15.0
        warnings.append("Excessive capitalization detected.")
        recommendations.append("Avoid shouting in ALL CAPS to improve readability and deliverability.")

    score = max(0.0, score)

    # Health status based on score
    if score >= 80:
        status = "Good"
    elif score >= 50:
        status = "Fair"
    else:
        status = "Poor"

    return {
        "score": score,
        "status": status,
        "warnings": warnings,
        "recommendations": recommendations,
        "details": {
            "spam_words_found": found_spam,
            "link_count": link_count,
            "word_count": word_count,
        }
    }

def get_deliverability_report(subject: str, body: str) -> Dict[str, Any]:
    """Generates a reusable report including score and full insights."""
    analysis = analyze_email_content(subject, body)
    return {
        "score": analysis["score"],
        "status": analysis["status"],
        "warnings": analysis["warnings"],
        "recommendations": analysis["recommendations"],
        "details": analysis["details"]
    }
