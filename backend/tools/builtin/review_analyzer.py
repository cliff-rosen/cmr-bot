"""
Review Analyzer Tool

Human-intuition-based review analysis that:
1. Reads ALL negative reviews (1-star, and 2-star if few 1-star)
2. Identifies patterns in complaints
3. Calculates ratios (good vs bad)
4. Detects anomalies (fake reviews, suspicious patterns)
5. Generates human-readable verdict with confidence score
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Generator, Literal, Tuple

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from services.serpapi_service import (
    get_serpapi_service,
    SerpApiBusiness,
    SerpApiReview,
    SerpApiResult
)

logger = logging.getLogger(__name__)

# Configuration
AGENT_MODEL = "claude-sonnet-4-20250514"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class RatingDistribution:
    """Distribution of reviews by star rating."""
    stars_1: int = 0
    stars_2: int = 0
    stars_3: int = 0
    stars_4: int = 0
    stars_5: int = 0
    total: int = 0

    @property
    def percent_1_star(self) -> float:
        return (self.stars_1 / self.total * 100) if self.total > 0 else 0.0

    @property
    def percent_2_star(self) -> float:
        return (self.stars_2 / self.total * 100) if self.total > 0 else 0.0

    @property
    def percent_negative(self) -> float:
        """1-2 stars as percentage"""
        return ((self.stars_1 + self.stars_2) / self.total * 100) if self.total > 0 else 0.0

    @property
    def percent_positive(self) -> float:
        """4-5 stars as percentage"""
        return ((self.stars_4 + self.stars_5) / self.total * 100) if self.total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stars_1": self.stars_1,
            "stars_2": self.stars_2,
            "stars_3": self.stars_3,
            "stars_4": self.stars_4,
            "stars_5": self.stars_5,
            "total": self.total,
            "percent_1_star": round(self.percent_1_star, 1),
            "percent_2_star": round(self.percent_2_star, 1),
            "percent_negative": round(self.percent_negative, 1),
            "percent_positive": round(self.percent_positive, 1)
        }


@dataclass
class ComplaintTheme:
    """A recurring complaint theme from negative reviews."""
    theme: str  # e.g., "Long wait times"
    frequency: int  # How many reviews mention this
    severity: Literal["critical", "moderate", "minor"]
    example_quotes: List[str] = field(default_factory=list)
    recent_trend: Literal["increasing", "stable", "decreasing", "unknown"] = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnomalyFlag:
    """A suspicious pattern detected in reviews."""
    type: Literal["fake_positive", "review_burst", "generic_text", "competitor_attack", "incentivized"]
    description: str
    evidence: List[str] = field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HumanIntuitionVerdict:
    """The final human-readable verdict."""
    recommendation: Literal["trustworthy", "proceed_with_caution", "significant_concerns", "avoid"]
    confidence: float  # 0-1
    summary: str  # 2-3 sentences
    key_concerns: List[str] = field(default_factory=list)
    positive_signals: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    overall_health_score: int = 50  # 0-100

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewArtifact:
    """A review for analysis."""
    rating: Optional[float]
    text: str
    author: Optional[str] = None
    date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AnalysisJourney:
    """Telemetry for the analysis process."""
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    phases: List[Dict[str, Any]] = field(default_factory=list)
    api_calls: int = 0
    reviews_analyzed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewAnalysisResult:
    """Complete result of human-intuition review analysis."""
    # Business info
    business_name: str
    business_url: str
    business_rating: Optional[float]
    business_review_count: Optional[int]
    source: str  # "yelp" or "google"

    # Phase 1: Overview
    rating_distribution: RatingDistribution

    # Phase 2: Negative Deep Dive
    negative_reviews: List[ReviewArtifact] = field(default_factory=list)
    one_star_count: int = 0
    two_star_count: int = 0

    # Phase 3: Positive Sample
    positive_sample: List[ReviewArtifact] = field(default_factory=list)

    # Phase 4: Analysis
    complaint_themes: List[ComplaintTheme] = field(default_factory=list)
    anomalies: List[AnomalyFlag] = field(default_factory=list)
    verdict: Optional[HumanIntuitionVerdict] = None

    # Journey
    journey: AnalysisJourney = field(default_factory=AnalysisJourney)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "business_name": self.business_name,
            "business_url": self.business_url,
            "business_rating": self.business_rating,
            "business_review_count": self.business_review_count,
            "source": self.source,
            "rating_distribution": self.rating_distribution.to_dict(),
            "negative_reviews": [r.to_dict() for r in self.negative_reviews],
            "one_star_count": self.one_star_count,
            "two_star_count": self.two_star_count,
            "positive_sample": [r.to_dict() for r in self.positive_sample],
            "complaint_themes": [t.to_dict() for t in self.complaint_themes],
            "anomalies": [a.to_dict() for a in self.anomalies],
            "verdict": self.verdict.to_dict() if self.verdict else None,
            "journey": self.journey.to_dict()
        }


# =============================================================================
# LLM Analysis Prompt
# =============================================================================

def _build_analysis_prompt(
    business_name: str,
    rating: float,
    review_count: int,
    distribution: RatingDistribution,
    negative_reviews: List[ReviewArtifact],
    positive_sample: List[ReviewArtifact]
) -> str:
    """Build the LLM prompt for analysis."""

    # Format negative reviews
    negative_text = ""
    for i, review in enumerate(negative_reviews[:50], 1):  # Cap at 50 for prompt size
        stars = int(review.rating) if review.rating else "?"
        date_str = f" ({review.date})" if review.date else ""
        negative_text += f"{i}. [{stars}-star]{date_str}: {review.text[:500]}\n\n"

    # Format positive reviews
    positive_text = ""
    for i, review in enumerate(positive_sample[:15], 1):
        date_str = f" ({review.date})" if review.date else ""
        positive_text += f"{i}. [5-star]{date_str}: {review.text[:300]}\n\n"

    return f"""You are analyzing reviews for "{business_name}" to provide a human-intuition-based verdict.

## Business Overview
- Overall Rating: {rating}/5
- Total Reviews: {review_count}
- Rating Distribution:
  - 1-star: {distribution.stars_1} ({distribution.percent_1_star:.1f}%)
  - 2-star: {distribution.stars_2} ({distribution.percent_2_star:.1f}%)
  - 3-star: {distribution.stars_3} (~{100 - distribution.percent_negative - distribution.percent_positive:.1f}%)
  - 4-star: {distribution.stars_4}
  - 5-star: {distribution.stars_5} ({distribution.percent_positive:.1f}%)

## All Negative Reviews ({len(negative_reviews)} total, showing up to 50)
{negative_text}

## Positive Review Sample ({len(positive_sample)} sampled)
{positive_text}

## Your Analysis Tasks

1. **Complaint Theme Extraction**: Identify 3-7 recurring complaint themes from negative reviews. For each:
   - theme: Short name (e.g., "Long wait times", "Poor communication")
   - frequency: Estimated number of reviews mentioning this
   - severity: "critical" (deal-breaker), "moderate" (concerning), or "minor" (annoyance)
   - example_quotes: 2-3 brief quotes from actual reviews
   - recent_trend: "increasing", "stable", "decreasing", or "unknown" based on dates

2. **Anomaly Detection**: Flag any suspicious patterns you notice:
   - fake_positive: Generic/templated positive reviews
   - review_burst: Many reviews posted in short time
   - generic_text: Suspiciously similar language across reviews
   - competitor_attack: Negative reviews that seem like sabotage
   - incentivized: Signs of incentivized/paid reviews

3. **Generate Verdict**: Based on your analysis:
   - recommendation: "trustworthy", "proceed_with_caution", "significant_concerns", or "avoid"
   - confidence: 0.0-1.0 (how confident in this assessment)
   - summary: 2-3 sentence human-readable summary
   - key_concerns: Top 3-5 specific concerns
   - positive_signals: Top 3-5 positive things
   - red_flags: Any deal-breakers (empty if none)
   - overall_health_score: 0-100 score

Output ONLY valid JSON in this exact format:
```json
{{
    "complaint_themes": [
        {{
            "theme": "string",
            "frequency": number,
            "severity": "critical|moderate|minor",
            "example_quotes": ["quote1", "quote2"],
            "recent_trend": "increasing|stable|decreasing|unknown"
        }}
    ],
    "anomalies": [
        {{
            "type": "fake_positive|review_burst|generic_text|competitor_attack|incentivized",
            "description": "string",
            "evidence": ["evidence1", "evidence2"],
            "confidence": "high|medium|low"
        }}
    ],
    "verdict": {{
        "recommendation": "trustworthy|proceed_with_caution|significant_concerns|avoid",
        "confidence": 0.85,
        "summary": "string",
        "key_concerns": ["concern1", "concern2"],
        "positive_signals": ["signal1", "signal2"],
        "red_flags": [],
        "overall_health_score": 75
    }}
}}
```"""


# =============================================================================
# Main Analysis Executor
# =============================================================================

def execute_review_analyzer(
    params: Dict[str, Any],
    db: Any,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Execute the human-intuition review analysis.

    4-Phase Strategy:
    1. Overview - Get business info and calculate distribution
    2. Negative Deep Dive - Fetch ALL 1-star (+ 2-star if few)
    3. Positive Sampling - Sample 5-star reviews
    4. LLM Analysis - Pattern detection, anomalies, verdict
    """
    business_name = params.get("business_name", "")
    location = params.get("location", "")
    source = params.get("source", "").lower()

    # Validate inputs
    if not business_name:
        return ToolResult(text="Error: business_name is required")
    if not location:
        return ToolResult(text="Error: location is required")
    if source not in ("yelp", "google"):
        return ToolResult(text="Error: source must be 'yelp' or 'google'")

    # Initialize journey tracking
    journey = AnalysisJourney()
    journey.started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    yield ToolProgress(
        stage="starting",
        message=f"Starting human-intuition analysis for {business_name}",
        data={"business_name": business_name, "source": source}
    )

    service = get_serpapi_service()
    if not service.api_key:
        return ToolResult(
            text="Error: SERPAPI_KEY not configured. Cannot analyze reviews."
        )

    # ==========================================================================
    # PHASE 1: Overview - Find business and get basic info
    # ==========================================================================

    yield ToolProgress(
        stage="phase1_overview",
        message="Phase 1: Getting business overview",
        data={"phase": 1}
    )

    journey.phases.append({"name": "overview", "started_at": datetime.now(timezone.utc).isoformat()})

    # Search for business
    if source == "yelp":
        search_result = service.search_yelp(business_name, location)
    else:
        search_result = service.search_google_maps(business_name, location)

    journey.api_calls += 1

    if not search_result.success or not search_result.business:
        journey.completed_at = datetime.now(timezone.utc).isoformat()
        journey.duration_ms = int((time.time() - start_time) * 1000)
        return ToolResult(
            text=f"Could not find {business_name} on {source.upper()}: {search_result.error}"
        )

    business = search_result.business

    # Estimate rating distribution from overall rating (will be refined)
    # This is approximate - we'll get actual counts from reviews
    distribution = RatingDistribution(
        total=business.review_count or 0
    )

    yield ToolProgress(
        stage="phase1_complete",
        message=f"Found: {business.name} ({business.rating}* / {business.review_count} reviews)",
        data={
            "business_name": business.name,
            "rating": business.rating,
            "review_count": business.review_count
        }
    )

    # ==========================================================================
    # PHASE 2: Negative Review Deep Dive
    # ==========================================================================

    yield ToolProgress(
        stage="phase2_negative",
        message="Phase 2: Fetching ALL negative reviews",
        data={"phase": 2}
    )

    journey.phases.append({"name": "negative_dive", "started_at": datetime.now(timezone.utc).isoformat()})

    negative_result = service.get_all_negative_reviews(
        place_id=business.place_id,
        source=source,
        max_reviews=100,
        include_2_star_if_few_1_star=True,
        min_1_star_threshold=5
    )

    journey.api_calls += 1  # Approximate - actual count varies with pagination

    if not negative_result.success:
        logger.warning(f"Failed to get negative reviews: {negative_result.error}")

    # Convert to our review format
    negative_reviews = []
    one_star_count = 0
    two_star_count = 0

    for r in negative_result.reviews:
        negative_reviews.append(ReviewArtifact(
            rating=r.rating,
            text=r.text,
            author=r.author,
            date=r.date
        ))
        if r.rating == 1:
            one_star_count += 1
        elif r.rating == 2:
            two_star_count += 1

    # Update distribution with actual counts
    distribution.stars_1 = one_star_count
    distribution.stars_2 = two_star_count

    yield ToolProgress(
        stage="phase2_complete",
        message=f"Found {len(negative_reviews)} negative reviews ({one_star_count} 1-star, {two_star_count} 2-star)",
        data={
            "negative_count": len(negative_reviews),
            "one_star": one_star_count,
            "two_star": two_star_count
        }
    )

    # ==========================================================================
    # PHASE 3: Positive Review Sampling
    # ==========================================================================

    yield ToolProgress(
        stage="phase3_positive",
        message="Phase 3: Sampling positive reviews",
        data={"phase": 3}
    )

    journey.phases.append({"name": "positive_sample", "started_at": datetime.now(timezone.utc).isoformat()})

    positive_result = service.get_positive_sample(
        place_id=business.place_id,
        source=source,
        num_reviews=20
    )

    journey.api_calls += 1

    positive_sample = []
    for r in positive_result.reviews:
        positive_sample.append(ReviewArtifact(
            rating=r.rating,
            text=r.text,
            author=r.author,
            date=r.date
        ))

    # Update distribution
    distribution.stars_5 = len(positive_sample)  # Approximate

    # Estimate remaining distribution
    if business.review_count:
        remaining = business.review_count - distribution.stars_1 - distribution.stars_2 - distribution.stars_5
        # Rough estimate: split remaining between 3 and 4 stars
        distribution.stars_3 = remaining // 3
        distribution.stars_4 = remaining - distribution.stars_3

    yield ToolProgress(
        stage="phase3_complete",
        message=f"Sampled {len(positive_sample)} 5-star reviews",
        data={"positive_count": len(positive_sample)}
    )

    # ==========================================================================
    # PHASE 4: LLM Analysis
    # ==========================================================================

    yield ToolProgress(
        stage="phase4_analysis",
        message="Phase 4: Analyzing patterns and generating verdict",
        data={"phase": 4}
    )

    journey.phases.append({"name": "llm_analysis", "started_at": datetime.now(timezone.utc).isoformat()})
    journey.reviews_analyzed = len(negative_reviews) + len(positive_sample)

    # Build and execute LLM analysis
    prompt = _build_analysis_prompt(
        business_name=business.name,
        rating=business.rating or 0,
        review_count=business.review_count or 0,
        distribution=distribution,
        negative_reviews=negative_reviews,
        positive_sample=positive_sample
    )

    # Call LLM for analysis
    import anthropic
    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=4096,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        # Parse JSON response
        analysis_data = _parse_llm_response(response_text)

    except Exception as e:
        logger.error(f"LLM analysis error: {e}")
        analysis_data = {
            "complaint_themes": [],
            "anomalies": [],
            "verdict": {
                "recommendation": "proceed_with_caution",
                "confidence": 0.3,
                "summary": f"Analysis incomplete due to error: {str(e)}",
                "key_concerns": ["Analysis could not be completed"],
                "positive_signals": [],
                "red_flags": [],
                "overall_health_score": 50
            }
        }

    # Parse complaint themes
    complaint_themes = []
    for theme_data in analysis_data.get("complaint_themes", []):
        complaint_themes.append(ComplaintTheme(
            theme=theme_data.get("theme", "Unknown"),
            frequency=theme_data.get("frequency", 0),
            severity=theme_data.get("severity", "moderate"),
            example_quotes=theme_data.get("example_quotes", []),
            recent_trend=theme_data.get("recent_trend", "unknown")
        ))

    # Parse anomalies
    anomalies = []
    for anomaly_data in analysis_data.get("anomalies", []):
        anomalies.append(AnomalyFlag(
            type=anomaly_data.get("type", "generic_text"),
            description=anomaly_data.get("description", ""),
            evidence=anomaly_data.get("evidence", []),
            confidence=anomaly_data.get("confidence", "low")
        ))

    # Parse verdict
    verdict_data = analysis_data.get("verdict", {})
    verdict = HumanIntuitionVerdict(
        recommendation=verdict_data.get("recommendation", "proceed_with_caution"),
        confidence=verdict_data.get("confidence", 0.5),
        summary=verdict_data.get("summary", "Analysis complete."),
        key_concerns=verdict_data.get("key_concerns", []),
        positive_signals=verdict_data.get("positive_signals", []),
        red_flags=verdict_data.get("red_flags", []),
        overall_health_score=verdict_data.get("overall_health_score", 50)
    )

    yield ToolProgress(
        stage="phase4_complete",
        message=f"Analysis complete: {verdict.recommendation.replace('_', ' ').title()}",
        data={
            "recommendation": verdict.recommendation,
            "health_score": verdict.overall_health_score,
            "themes_found": len(complaint_themes),
            "anomalies_found": len(anomalies)
        }
    )

    # ==========================================================================
    # Build Final Result
    # ==========================================================================

    journey.completed_at = datetime.now(timezone.utc).isoformat()
    journey.duration_ms = int((time.time() - start_time) * 1000)

    result = ReviewAnalysisResult(
        business_name=business.name,
        business_url=business.url or "",
        business_rating=business.rating,
        business_review_count=business.review_count,
        source=source,
        rating_distribution=distribution,
        negative_reviews=negative_reviews,
        one_star_count=one_star_count,
        two_star_count=two_star_count,
        positive_sample=positive_sample,
        complaint_themes=complaint_themes,
        anomalies=anomalies,
        verdict=verdict,
        journey=journey
    )

    yield ToolProgress(
        stage="complete",
        message=f"Analysis complete for {business.name}",
        data={"success": True}
    )

    return ToolResult(
        text=_format_text_output(result),
        data=result.to_dict(),
        workspace_payload={
            "type": "review_analysis",
            "title": f"Review Analysis: {business.name}",
            "content": verdict.summary if verdict else "Analysis complete",
            "data": result.to_dict()
        }
    )


def _parse_llm_response(response_text: str) -> Dict[str, Any]:
    """Parse JSON from LLM response."""
    # Try to extract JSON from markdown code block
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try parsing entire response as JSON
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Return empty structure
    return {"complaint_themes": [], "anomalies": [], "verdict": {}}


def _format_text_output(result: ReviewAnalysisResult) -> str:
    """Format result as human-readable text."""
    lines = []

    # Header
    lines.append(f"## Review Analysis: {result.business_name}")
    lines.append(f"**Source:** {result.source.upper()} | **Rating:** {result.business_rating}/5 | **Reviews:** {result.business_review_count}")
    lines.append("")

    # Verdict
    if result.verdict:
        v = result.verdict
        recommendation_emoji = {
            "trustworthy": "o",
            "proceed_with_caution": "!",
            "significant_concerns": "!!",
            "avoid": "X"
        }.get(v.recommendation, "?")

        lines.append(f"### [{recommendation_emoji}] {v.recommendation.replace('_', ' ').upper()} (Score: {v.overall_health_score}/100)")
        lines.append(f"{v.summary}")
        lines.append("")

    # Rating Distribution
    d = result.rating_distribution
    lines.append("### Rating Distribution")
    lines.append(f"- 1-star: {d.stars_1} ({d.percent_1_star:.1f}%)")
    lines.append(f"- 2-star: {d.stars_2} ({d.percent_2_star:.1f}%)")
    lines.append(f"- 5-star: {d.stars_5}")
    lines.append(f"- Negative rate: {d.percent_negative:.1f}%")
    lines.append("")

    # Complaint Themes
    if result.complaint_themes:
        lines.append(f"### Complaint Themes ({len(result.negative_reviews)} negative reviews analyzed)")
        for i, theme in enumerate(result.complaint_themes, 1):
            severity_indicator = {"critical": "[!]", "moderate": "[*]", "minor": "[-]"}.get(theme.severity, "")
            trend = {"increasing": "^", "decreasing": "v", "stable": "-", "unknown": "?"}.get(theme.recent_trend, "?")
            lines.append(f"{i}. {theme.theme} {severity_indicator} - {theme.frequency} mentions {trend}")
            if theme.example_quotes:
                lines.append(f'   "{theme.example_quotes[0][:100]}..."')
        lines.append("")

    # Anomalies
    if result.anomalies:
        lines.append("### Anomalies Detected")
        for anomaly in result.anomalies:
            lines.append(f"- [{anomaly.confidence.upper()}] {anomaly.type}: {anomaly.description}")
        lines.append("")

    # Key Findings
    if result.verdict:
        if result.verdict.key_concerns:
            lines.append("### Key Concerns")
            for concern in result.verdict.key_concerns:
                lines.append(f"- {concern}")
            lines.append("")

        if result.verdict.positive_signals:
            lines.append("### Positive Signals")
            for signal in result.verdict.positive_signals:
                lines.append(f"- {signal}")
            lines.append("")

        if result.verdict.red_flags:
            lines.append("### RED FLAGS")
            for flag in result.verdict.red_flags:
                lines.append(f"- {flag}")
            lines.append("")

    # Journey
    lines.append(f"### Analysis Stats")
    lines.append(f"- Duration: {result.journey.duration_ms}ms")
    lines.append(f"- API Calls: {result.journey.api_calls}")
    lines.append(f"- Reviews Analyzed: {result.journey.reviews_analyzed}")

    return "\n".join(lines)


# =============================================================================
# Tool Registration
# =============================================================================

REVIEW_ANALYZER_TOOL = ToolConfig(
    name="analyze_reviews",
    description="""Perform deep human-intuition-based analysis of business reviews.

This tool goes beyond basic review collection to:
1. Read ALL negative reviews (1-star, and 2-star if few 1-star exist)
2. Identify recurring complaint themes with severity ratings
3. Detect anomalies (fake reviews, suspicious patterns)
4. Generate a human-readable verdict with confidence score

Use this when you need to thoroughly evaluate a business's reputation,
not just collect reviews. Returns analysis with recommendation:
- trustworthy: Safe to use
- proceed_with_caution: Some concerns but generally ok
- significant_concerns: Major issues identified
- avoid: Red flags detected

Currently supports Yelp and Google reviews.""",
    input_schema={
        "type": "object",
        "properties": {
            "business_name": {
                "type": "string",
                "description": "Name of the business to analyze"
            },
            "location": {
                "type": "string",
                "description": "City and state (e.g., 'Cambridge, MA')"
            },
            "source": {
                "type": "string",
                "enum": ["yelp", "google"],
                "description": "Review source to analyze (yelp or google)"
            }
        },
        "required": ["business_name", "location", "source"]
    },
    executor=execute_review_analyzer,
    category="research",
    streaming=True
)


def register_review_analyzer_tool():
    """Register the review analyzer tool."""
    register_tool(REVIEW_ANALYZER_TOOL)
    logger.info("Registered analyze_reviews tool")
