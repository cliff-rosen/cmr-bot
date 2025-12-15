"""
Vendor Finder Workflow Template

A structured workflow for finding and evaluating vendors/service providers.
Builds a list of vendors with company info, reviews, and ratings.

Data structure: List of vendors with:
- Name, website, description
- Location, contact info
- Reviews from Yelp, Google, Reddit
- Rating, sentiment summary
- User notes and status

Graph structure:
    [define_criteria] -> [criteria_checkpoint] -> [broad_search] -> [build_vendor_list]
         -> [vendor_list_checkpoint] -> [enrich_company_info] -> [find_reviews]
         -> [final_checkpoint]
"""

import logging
import json
import asyncio
from typing import Any, Dict, List, Optional, AsyncGenerator, Union
from dataclasses import dataclass, asdict
import anthropic

from schemas.workflow import (
    WorkflowGraph,
    StepNode,
    Edge,
    StepOutput,
    StepProgress,
    CheckpointConfig,
    CheckpointAction,
    WorkflowContext,
)

logger = logging.getLogger(__name__)

# LLM client
_client = None
MODEL = "claude-sonnet-4-20250514"


def get_llm_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _parse_json(text: str) -> Optional[Any]:
    """Parse JSON from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start_idx = 1
        end_idx = len(lines)
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[start_idx:end_idx]).strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}")
        return None


# =============================================================================
# Vendor Data Structure
# =============================================================================

@dataclass
class ReviewSummary:
    """Summary of reviews from a source."""
    source: str  # "yelp", "google", "reddit"
    rating: Optional[float] = None  # 1-5 scale
    review_count: int = 0
    sentiment: str = "unknown"  # "positive", "mixed", "negative", "unknown"
    highlights: List[str] = None  # Key positive points
    concerns: List[str] = None  # Key negative points
    sample_quotes: List[str] = None

    def __post_init__(self):
        self.highlights = self.highlights or []
        self.concerns = self.concerns or []
        self.sample_quotes = self.sample_quotes or []


@dataclass
class Vendor:
    """A vendor/service provider entry."""
    id: str
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    services: List[str] = None
    location: Optional[str] = None
    contact: Dict[str, str] = None  # phone, email, address
    price_tier: Optional[str] = None  # "$", "$$", "$$$", "$$$$"
    reviews: List[ReviewSummary] = None
    overall_rating: Optional[float] = None
    overall_sentiment: str = "unknown"
    status: str = "pending"  # "pending", "approved", "rejected", "shortlisted"
    user_notes: Optional[str] = None
    source_urls: List[str] = None

    def __post_init__(self):
        self.services = self.services or []
        self.contact = self.contact or {}
        self.reviews = self.reviews or []
        self.source_urls = self.source_urls or []

    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization."""
        data = asdict(self)
        # Convert ReviewSummary objects
        data["reviews"] = [asdict(r) if isinstance(r, ReviewSummary) else r for r in self.reviews]
        return data


# =============================================================================
# Step Implementations
# =============================================================================

async def define_criteria(context: WorkflowContext) -> StepOutput:
    """
    Step 1: Define search criteria from user input.
    """
    user_query = context.initial_input.get("query", "")
    location = context.initial_input.get("location", "")
    requirements = context.initial_input.get("requirements", "")

    if not user_query:
        return StepOutput(success=False, error="No query provided")

    try:
        client = get_llm_client()

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""I need to find vendors/service providers. Help me define clear search criteria.

User's request: "{user_query}"
Location (if specified): "{location}"
Additional requirements: "{requirements}"

Please structure this into:
1. Type of vendor/service (be specific)
2. Geographic scope (if applicable)
3. Key requirements/features needed
4. Nice-to-have features
5. Budget considerations (if mentioned)
6. Any deal-breakers or things to avoid

Return JSON:
{{
    "vendor_type": "specific type of vendor",
    "vendor_type_alternatives": ["alternative names/types to search"],
    "location": "city/region or 'remote'/'any'",
    "radius": "local/regional/national/international",
    "must_have": ["requirement 1", "requirement 2"],
    "nice_to_have": ["feature 1", "feature 2"],
    "budget_hint": "any budget info or 'not specified'",
    "avoid": ["things to avoid"],
    "search_queries": ["query 1 to search", "query 2 to search", "query 3 to search"]
}}

JSON:"""
            }]
        )

        data = _parse_json(response.content[0].text)
        if not data:
            data = {
                "vendor_type": user_query,
                "vendor_type_alternatives": [],
                "location": location or "any",
                "radius": "local" if location else "any",
                "must_have": [],
                "nice_to_have": [],
                "budget_hint": "not specified",
                "avoid": [],
                "search_queries": [user_query, f"{user_query} near {location}"] if location else [user_query]
            }

        display = f"""## Search Criteria

**Vendor Type:** {data.get('vendor_type', user_query)}
**Location:** {data.get('location', 'Any')} ({data.get('radius', 'any')})

**Must Have:**
{chr(10).join(f'- {r}' for r in data.get('must_have', [])) or '- None specified'}

**Nice to Have:**
{chr(10).join(f'- {r}' for r in data.get('nice_to_have', [])) or '- None specified'}

**Budget:** {data.get('budget_hint', 'Not specified')}

**Search Queries to Use:**
{chr(10).join(f'- {q}' for q in data.get('search_queries', []))}
"""

        return StepOutput(
            success=True,
            data={
                "original_query": user_query,
                "criteria": data
            },
            display_title="Search Criteria Defined",
            display_content=display,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error defining criteria")
        return StepOutput(success=False, error=str(e))


async def broad_search(context: WorkflowContext) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Step 2: Execute broad search to find potential vendors.
    """
    from services.search_service import SearchService

    criteria_data = context.get_step_output("define_criteria")
    if not criteria_data:
        yield StepOutput(success=False, error="No criteria data")
        return

    # Check for user edits from checkpoint
    user_edits = context.user_edits.get("criteria_checkpoint", {})
    criteria = user_edits.get("criteria") or criteria_data.get("criteria", {})

    search_queries = criteria.get("search_queries", [criteria_data.get("original_query", "")])
    location = criteria.get("location", "")

    yield StepProgress(message="Starting vendor search...", progress=0.1)

    try:
        search_service = SearchService()
        if not search_service.initialized:
            search_service.initialize()

        all_results = []

        for i, query in enumerate(search_queries[:5]):  # Max 5 queries
            yield StepProgress(
                message=f"Searching: {query[:40]}...",
                progress=0.1 + (i / len(search_queries)) * 0.6
            )

            try:
                result = await search_service.search(search_term=query, num_results=15)
                for item in result.get("search_results", []):
                    # Dedupe by URL
                    if not any(r["url"] == item.url for r in all_results):
                        all_results.append({
                            "title": item.title,
                            "url": item.url,
                            "snippet": item.snippet,
                            "query": query
                        })
            except Exception as e:
                logger.warning(f"Search error for '{query}': {e}")

        yield StepProgress(message=f"Found {len(all_results)} results", progress=0.8)

        display = f"## Search Results\n\nFound **{len(all_results)}** potential vendors\n\n"
        for i, r in enumerate(all_results[:10], 1):
            display += f"{i}. **{r['title']}**\n   {r['snippet'][:120]}...\n\n"

        yield StepOutput(
            success=True,
            data={
                **criteria_data,
                "search_results": all_results
            },
            display_title="Search Complete",
            display_content=display,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Broad search error")
        yield StepOutput(success=False, error=str(e))


async def build_vendor_list(context: WorkflowContext) -> StepOutput:
    """
    Step 3: Parse search results into structured vendor list.
    """
    search_data = context.get_step_output("broad_search")
    if not search_data:
        return StepOutput(success=False, error="No search data")

    results = search_data.get("search_results", [])
    criteria = search_data.get("criteria", {})

    if not results:
        return StepOutput(
            success=True,
            data={**search_data, "vendors": []},
            display_title="No Vendors Found",
            display_content="No search results to build vendor list from."
        )

    try:
        client = get_llm_client()

        # Have LLM extract vendor info from search results
        results_text = ""
        for i, r in enumerate(results[:20], 1):
            results_text += f"{i}. {r['title']}\n   URL: {r['url']}\n   {r['snippet']}\n\n"

        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Extract vendor information from these search results.

We're looking for: {criteria.get('vendor_type', 'vendors')}
Location: {criteria.get('location', 'any')}

Search results:
{results_text}

For each distinct vendor/company found, extract:
- name: company name
- website: their main website URL (if identifiable)
- description: what they do (brief)
- location: where they're based (if mentioned)

Filter out:
- Aggregator/directory sites (just list vendors, not actual vendors)
- Irrelevant results (not the type of vendor we're looking for)
- Duplicate entries

Return JSON:
{{
    "vendors": [
        {{
            "name": "Company Name",
            "website": "https://...",
            "description": "What they do",
            "location": "City, State"
        }}
    ]
}}

JSON:"""
            }]
        )

        data = _parse_json(response.content[0].text)
        if not data or not data.get("vendors"):
            data = {"vendors": []}

        # Convert to Vendor objects
        vendors = []
        for i, v in enumerate(data.get("vendors", [])[:15]):  # Max 15 vendors
            vendor = Vendor(
                id=f"vendor_{i+1}",
                name=v.get("name", f"Vendor {i+1}"),
                website=v.get("website"),
                description=v.get("description"),
                location=v.get("location"),
                status="pending"
            )
            vendors.append(vendor.to_dict())

        display = f"## Vendor List ({len(vendors)} found)\n\n"
        for v in vendors:
            display += f"### {v['name']}\n"
            if v.get('website'):
                display += f"Website: {v['website']}\n"
            if v.get('description'):
                display += f"{v['description']}\n"
            if v.get('location'):
                display += f"Location: {v['location']}\n"
            display += "\n"

        return StepOutput(
            success=True,
            data={
                **search_data,
                "vendors": vendors,
                "vendor_count": len(vendors)
            },
            display_title=f"Found {len(vendors)} Vendors",
            display_content=display,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error building vendor list")
        return StepOutput(success=False, error=str(e))


async def enrich_company_info(context: WorkflowContext) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Step 4: Visit vendor websites to enrich company information.
    """
    from services.web_retrieval_service import WebRetrievalService

    vendor_data = context.get_step_output("build_vendor_list")
    if not vendor_data:
        yield StepOutput(success=False, error="No vendor data")
        return

    vendors = vendor_data.get("vendors", [])

    # Filter to approved vendors (or all if no checkpoint filtering yet)
    approved_vendors = [v for v in vendors if v.get("status") in ["pending", "approved", "shortlisted"]]

    if not approved_vendors:
        yield StepOutput(
            success=True,
            data=vendor_data,
            display_title="No Vendors to Enrich",
            display_content="No vendors selected for detailed research."
        )
        return

    yield StepProgress(message=f"Enriching {len(approved_vendors)} vendors...", progress=0.1)

    web_service = WebRetrievalService()
    client = get_llm_client()

    enriched_vendors = []

    for i, vendor in enumerate(approved_vendors):
        yield StepProgress(
            message=f"Researching: {vendor['name']}",
            progress=0.1 + (i / len(approved_vendors)) * 0.8
        )

        website = vendor.get("website")
        if not website:
            enriched_vendors.append(vendor)
            continue

        try:
            # Fetch their website
            result = await web_service.retrieve_webpage(url=website, extract_text_only=True)
            webpage = result["webpage"]
            content = webpage.content[:6000]

            # Extract info with LLM
            response = client.messages.create(
                model=MODEL,
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": f"""Extract company information from this website content:

Company: {vendor['name']}
URL: {website}

Content:
{content}

Extract and return JSON:
{{
    "description": "updated description of what they do",
    "services": ["service 1", "service 2"],
    "contact": {{"phone": "...", "email": "...", "address": "..."}},
    "price_tier": "$/$$/$$$/$$$$" or null
}}

Only include fields you can actually find. JSON:"""
                }]
            )

            extracted = _parse_json(response.content[0].text)
            if extracted:
                vendor["description"] = extracted.get("description", vendor.get("description"))
                vendor["services"] = extracted.get("services", [])
                vendor["contact"] = extracted.get("contact", {})
                vendor["price_tier"] = extracted.get("price_tier")
                vendor["source_urls"] = vendor.get("source_urls", []) + [website]

        except Exception as e:
            logger.warning(f"Failed to enrich {vendor['name']}: {e}")

        enriched_vendors.append(vendor)

    yield StepProgress(message="Company info enriched", progress=0.95)

    display = f"## Enriched Vendor Profiles\n\n"
    for v in enriched_vendors:
        display += f"### {v['name']}\n"
        if v.get('description'):
            display += f"{v['description']}\n\n"
        if v.get('services'):
            display += f"**Services:** {', '.join(v['services'])}\n"
        if v.get('price_tier'):
            display += f"**Price:** {v['price_tier']}\n"
        if v.get('contact'):
            contacts = [f"{k}: {v}" for k, v in v['contact'].items() if v]
            if contacts:
                display += f"**Contact:** {', '.join(contacts)}\n"
        display += "\n"

    yield StepOutput(
        success=True,
        data={
            **vendor_data,
            "vendors": enriched_vendors
        },
        display_title="Vendors Enriched",
        display_content=display,
        content_type="markdown"
    )


async def find_reviews(context: WorkflowContext) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Step 5: Search for reviews on Yelp, Google, Reddit.
    """
    from services.search_service import SearchService

    vendor_data = context.get_step_output("enrich_company_info")
    if not vendor_data:
        yield StepOutput(success=False, error="No vendor data")
        return

    vendors = vendor_data.get("vendors", [])

    if not vendors:
        yield StepOutput(success=True, data=vendor_data, display_title="No Vendors", display_content="No vendors to find reviews for.")
        return

    yield StepProgress(message=f"Searching reviews for {len(vendors)} vendors...", progress=0.1)

    search_service = SearchService()
    if not search_service.initialized:
        search_service.initialize()

    client = get_llm_client()
    reviewed_vendors = []

    for i, vendor in enumerate(vendors):
        yield StepProgress(
            message=f"Finding reviews: {vendor['name']}",
            progress=0.1 + (i / len(vendors)) * 0.8
        )

        vendor_name = vendor["name"]
        location = vendor.get("location", "")

        reviews = []

        # Search for Yelp reviews
        try:
            yelp_query = f"{vendor_name} yelp reviews {location}".strip()
            yelp_results = await search_service.search(search_term=yelp_query, num_results=5)

            yelp_snippets = "\n".join(
                f"- {r.snippet}" for r in yelp_results.get("search_results", [])[:3]
            )

            if yelp_snippets:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=256,
                    messages=[{
                        "role": "user",
                        "content": f"""Summarize Yelp reviews for {vendor_name}:

{yelp_snippets}

Return JSON:
{{"rating": 4.5, "sentiment": "positive/mixed/negative", "highlights": ["good point"], "concerns": ["issue"]}}
JSON:"""
                    }]
                )
                yelp_data = _parse_json(response.content[0].text) or {}
                reviews.append(ReviewSummary(
                    source="yelp",
                    rating=yelp_data.get("rating"),
                    sentiment=yelp_data.get("sentiment", "unknown"),
                    highlights=yelp_data.get("highlights", []),
                    concerns=yelp_data.get("concerns", [])
                ))
        except Exception as e:
            logger.warning(f"Yelp search error for {vendor_name}: {e}")

        # Search for Google reviews
        try:
            google_query = f'"{vendor_name}" reviews {location}'.strip()
            google_results = await search_service.search(search_term=google_query, num_results=5)

            google_snippets = "\n".join(
                f"- {r.snippet}" for r in google_results.get("search_results", [])[:3]
            )

            if google_snippets:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=256,
                    messages=[{
                        "role": "user",
                        "content": f"""Summarize Google/general reviews for {vendor_name}:

{google_snippets}

Return JSON:
{{"rating": 4.5, "sentiment": "positive/mixed/negative", "highlights": ["good point"], "concerns": ["issue"]}}
JSON:"""
                    }]
                )
                google_data = _parse_json(response.content[0].text) or {}
                reviews.append(ReviewSummary(
                    source="google",
                    rating=google_data.get("rating"),
                    sentiment=google_data.get("sentiment", "unknown"),
                    highlights=google_data.get("highlights", []),
                    concerns=google_data.get("concerns", [])
                ))
        except Exception as e:
            logger.warning(f"Google review search error for {vendor_name}: {e}")

        # Search Reddit for mentions
        try:
            reddit_query = f'site:reddit.com "{vendor_name}"'
            reddit_results = await search_service.search(search_term=reddit_query, num_results=5)

            reddit_snippets = "\n".join(
                f"- {r.snippet}" for r in reddit_results.get("search_results", [])[:3]
            )

            if reddit_snippets:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=256,
                    messages=[{
                        "role": "user",
                        "content": f"""Summarize Reddit mentions for {vendor_name}:

{reddit_snippets}

Return JSON:
{{"sentiment": "positive/mixed/negative", "highlights": ["good point"], "concerns": ["issue"]}}
JSON:"""
                    }]
                )
                reddit_data = _parse_json(response.content[0].text) or {}
                reviews.append(ReviewSummary(
                    source="reddit",
                    sentiment=reddit_data.get("sentiment", "unknown"),
                    highlights=reddit_data.get("highlights", []),
                    concerns=reddit_data.get("concerns", [])
                ))
        except Exception as e:
            logger.warning(f"Reddit search error for {vendor_name}: {e}")

        # Convert ReviewSummary to dicts for JSON serialization
        vendor["reviews"] = [asdict(r) for r in reviews]

        # Calculate overall sentiment
        sentiments = [r.sentiment for r in reviews if r.sentiment != "unknown"]
        if sentiments:
            pos_count = sentiments.count("positive")
            neg_count = sentiments.count("negative")
            if pos_count > neg_count:
                vendor["overall_sentiment"] = "positive"
            elif neg_count > pos_count:
                vendor["overall_sentiment"] = "negative"
            else:
                vendor["overall_sentiment"] = "mixed"

        # Calculate overall rating
        ratings = [r.rating for r in reviews if r.rating is not None]
        if ratings:
            vendor["overall_rating"] = round(sum(ratings) / len(ratings), 1)

        reviewed_vendors.append(vendor)

    yield StepProgress(message="Reviews collected", progress=0.95)

    # Build display
    display = "## Vendor Reviews Summary\n\n"
    for v in reviewed_vendors:
        display += f"### {v['name']}"
        if v.get('overall_rating'):
            display += f" ({v['overall_rating']}/5)"
        if v.get('overall_sentiment'):
            emoji = {"positive": "👍", "mixed": "😐", "negative": "👎"}.get(v['overall_sentiment'], "")
            display += f" {emoji}"
        display += "\n"

        for review in v.get('reviews', []):
            display += f"\n**{review['source'].title()}:**"
            if review.get('rating'):
                display += f" {review['rating']}/5"
            display += f" ({review.get('sentiment', 'unknown')})\n"
            if review.get('highlights'):
                display += f"  + {', '.join(review['highlights'][:2])}\n"
            if review.get('concerns'):
                display += f"  - {', '.join(review['concerns'][:2])}\n"

        display += "\n"

    yield StepOutput(
        success=True,
        data={
            **vendor_data,
            "vendors": reviewed_vendors
        },
        display_title="Reviews Complete",
        display_content=display,
        content_type="markdown"
    )


# =============================================================================
# Workflow Graph Definition
# =============================================================================

vendor_finder_workflow = WorkflowGraph(
    id="vendor_finder",
    name="Vendor Finder",
    description="Find and evaluate vendors/service providers with reviews and ratings",
    icon="building-storefront",
    category="research",

    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What type of vendor are you looking for?"
            },
            "location": {
                "type": "string",
                "description": "Location/area (optional)"
            },
            "requirements": {
                "type": "string",
                "description": "Specific requirements (optional)"
            }
        },
        "required": ["query"]
    },

    output_schema={
        "type": "object",
        "properties": {
            "vendors": {
                "type": "array",
                "items": {"type": "object"}
            }
        }
    },

    entry_node="define_criteria",

    nodes={
        "define_criteria": StepNode(
            id="define_criteria",
            name="Define Search Criteria",
            description="Refine vendor search criteria",
            node_type="execute",
            execute_fn=define_criteria,
            ui_component="criteria_stage"
        ),

        "criteria_checkpoint": StepNode(
            id="criteria_checkpoint",
            name="Review Criteria",
            description="Review and approve search criteria",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Search Criteria",
                description="Review the search criteria before we start finding vendors.",
                allowed_actions=[CheckpointAction.APPROVE, CheckpointAction.EDIT, CheckpointAction.REJECT],
                editable_fields=["criteria"]
            ),
            ui_component="criteria_stage"
        ),

        "broad_search": StepNode(
            id="broad_search",
            name="Broad Search",
            description="Search for potential vendors",
            node_type="execute",
            execute_fn=broad_search,
            ui_component="search_stage"
        ),

        "build_vendor_list": StepNode(
            id="build_vendor_list",
            name="Build Vendor List",
            description="Parse results into structured vendor list",
            node_type="execute",
            execute_fn=build_vendor_list,
            ui_component="vendor_list_stage"
        ),

        "vendor_list_checkpoint": StepNode(
            id="vendor_list_checkpoint",
            name="Review Vendor List",
            description="Review and select vendors for deep dive",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Vendor List",
                description="Review the vendor list. Approve vendors to research their reviews, or reject to exclude.",
                allowed_actions=[CheckpointAction.APPROVE, CheckpointAction.REJECT],
                editable_fields=[]
            ),
            ui_component="vendor_list_stage"
        ),

        "enrich_company_info": StepNode(
            id="enrich_company_info",
            name="Enrich Company Info",
            description="Visit vendor websites for detailed info",
            node_type="execute",
            execute_fn=enrich_company_info,
            ui_component="enrich_stage"
        ),

        "find_reviews": StepNode(
            id="find_reviews",
            name="Find Reviews",
            description="Search for reviews on Yelp, Google, Reddit",
            node_type="execute",
            execute_fn=find_reviews,
            ui_component="reviews_stage"
        ),

        "final_checkpoint": StepNode(
            id="final_checkpoint",
            name="Final Review",
            description="Review complete vendor profiles",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Vendor Research",
                description="Review the complete vendor profiles with reviews and ratings.",
                allowed_actions=[CheckpointAction.APPROVE, CheckpointAction.REJECT],
                editable_fields=[]
            ),
            ui_component="final_stage"
        ),
    },

    edges=[
        Edge(from_node="define_criteria", to_node="criteria_checkpoint"),
        Edge(from_node="criteria_checkpoint", to_node="broad_search"),
        Edge(from_node="broad_search", to_node="build_vendor_list"),
        Edge(from_node="build_vendor_list", to_node="vendor_list_checkpoint"),
        Edge(from_node="vendor_list_checkpoint", to_node="enrich_company_info"),
        Edge(from_node="enrich_company_info", to_node="find_reviews"),
        Edge(from_node="find_reviews", to_node="final_checkpoint"),
        # final_checkpoint has no outgoing edges = workflow complete
    ]
)
