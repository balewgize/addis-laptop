"""LLM-based recommendation engine with pros/cons analysis."""

import json
import logging

import httpx

from .config import Settings, get_settings
from .database import Database
from .schemas import (
    LaptopDB,
    LaptopRecommendation,
    RecommendationRequest,
    RecommendationResponse,
    SearchFilters,
)

logger = logging.getLogger(__name__)

RECOMMENDATION_SYSTEM_PROMPT = """You are a laptop buying advisor for Ethiopian consumers.

Your job is to analyze laptops and provide clear, honest recommendations with pros and cons.

Context:
- Prices are in ETB (Ethiopian Birr)
- Users are typically looking for value for money
- Common use cases: programming, office work, students, gaming, video editing
- Be honest about limitations - don't oversell

Output valid JSON only."""

RECOMMENDATION_USER_PROMPT = """A user is looking for a laptop with these requirements:

{user_requirements}

Here are the available laptops (from Ethiopian Telegram channels):

{laptops_json}

Analyze these laptops and recommend the TOP 3 best matches.

For each recommendation, provide:
- rank (1, 2, or 3)
- laptop_id (from the data)
- pros (list of 2-4 strengths relevant to user's needs)
- cons (list of 1-3 weaknesses or concerns)
- verdict (concise one sentence summary why this laptop fits)
- best_for (who should buy this, e.g., "Best for students", "Best value")

Also provide:
- query_summary (short one sentence summarizing what the user wants)
- market_insight (optional: observation about pricing/availability, or null)

Return JSON in this exact format:
{{
    "query_summary": "...",
    "market_insight": "..." or null,
    "recommendations": [
        {{
            "rank": 1,
            "laptop_id": 123,
            "pros": ["...", "..."],
            "cons": ["..."],
            "verdict": "...",
            "best_for": "..."
        }}
    ]
}}

If fewer than 3 laptops match well, only include those that are good fits.
JSON only, no explanation:"""


class LLMRecommender:
    """Generates laptop recommendations using LLM analysis."""

    def __init__(
        self,
        database: Database | None = None,
        settings: Settings | None = None,
    ):
        self.db = database or Database()
        self.settings = settings or get_settings()
        self.client = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        logger.info("LLMRecommender initialized")

    def recommend(
        self,
        request: RecommendationRequest,
        limit: int = 3,
    ) -> RecommendationResponse:
        """Get LLM-powered recommendations with pros/cons."""
        logger.info(f"Generating recommendations for: {request.model_dump()}")

        candidates = self._get_candidates(request)

        if not candidates:
            logger.warning("No candidates found for request")
            return RecommendationResponse(
                query_summary="No laptops match your criteria",
                recommendations=[],
                market_insight="Try adjusting your budget or requirements",
            )

        logger.info(f"Found {len(candidates)} candidate laptops")

        user_requirements = self._format_requirements(request)
        laptops_json = self._format_laptops_for_llm(candidates)

        llm_response = self._call_llm(user_requirements, laptops_json)

        if not llm_response:
            logger.error("LLM recommendation failed, using fallback")
            return self._fallback_recommendations(candidates, request, limit)

        return self._build_response(llm_response, candidates)

    def _get_candidates(
        self,
        request: RecommendationRequest,
        max_candidates: int = 20,
    ) -> list[LaptopDB]:
        """Get candidate laptops from database."""
        filters = SearchFilters(
            brand=request.brand_preference,
            min_price=request.budget_min,
            max_price=request.budget_max,
            posted_within_days=90,
        )

        laptops = self.db.search_laptops(filters)

        def completeness_score(laptop: LaptopDB) -> int:
            score = 0
            if laptop.price_etb:
                score += 3
            if laptop.ram_gb:
                score += 2
            if laptop.storage_gb:
                score += 2
            if laptop.cpu:
                score += 1
            if laptop.contact:
                score += 1
            return score

        laptops.sort(key=completeness_score, reverse=True)
        return laptops[:max_candidates]

    def _format_requirements(self, request: RecommendationRequest) -> str:
        """Format user requirements as readable text."""
        parts = []

        if request.budget_max:
            if request.budget_min:
                parts.append(
                    f"Budget: {request.budget_min:,.0f} - {request.budget_max:,.0f} ETB"
                )
            else:
                parts.append(f"Budget: Up to {request.budget_max:,.0f} ETB")
        elif request.budget_min:
            parts.append(f"Budget: At least {request.budget_min:,.0f} ETB")

        if request.use_case:
            parts.append(f"Use case: {request.use_case}")

        if request.priorities:
            parts.append(f"Priorities: {', '.join(request.priorities)}")

        if request.brand_preference:
            parts.append(f"Preferred brand: {request.brand_preference}")

        if not parts:
            parts.append("General purpose laptop, best value for money")

        return "\n".join(parts)

    def _format_laptops_for_llm(self, laptops: list[LaptopDB]) -> str:
        """Format laptops as JSON for LLM input."""
        laptop_data = []

        for laptop in laptops:
            data = {
                "id": laptop.id,
                "brand": laptop.brand,
                "model": laptop.model,
                "cpu": laptop.cpu,
                "ram_gb": laptop.ram_gb,
                "storage_gb": laptop.storage_gb,
                "storage_type": laptop.storage_type,
                "screen_size": laptop.screen_size,
                "gpu": laptop.gpu,
                "price_etb": laptop.price_etb,
                "condition": laptop.condition,
                "battery_life": laptop.battery_life,
                "posted_date": laptop.posted_at.strftime("%Y-%m-%d"),
                "channel": laptop.channel.split("/")[-1],
            }
            data = {k: v for k, v in data.items() if v is not None}
            laptop_data.append(data)

        return json.dumps(laptop_data, indent=2)

    def _call_llm(self, user_requirements: str, laptops_json: str) -> dict | None:
        """Call LLM for recommendation analysis."""
        try:
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": self.settings.llm_model,
                    "messages": [
                        {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": RECOMMENDATION_USER_PROMPT.format(
                                user_requirements=user_requirements,
                                laptops_json=laptops_json,
                            ),
                        },
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"LLM response: {content[:500]}...")

            return self._parse_llm_response(content)

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _parse_llm_response(self, content: str) -> dict | None:
        """Parse JSON from LLM response."""
        content = content.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            lines = [line for line in lines if not line.startswith("```")]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse LLM JSON: {content[:200]}...")
                    return None
            return None

    def _build_response(
        self,
        llm_response: dict,
        candidates: list[LaptopDB],
    ) -> RecommendationResponse:
        """Build final response from LLM output."""
        laptop_map = {laptop.id: laptop for laptop in candidates}

        recommendations = []
        for rec in llm_response.get("recommendations", []):
            laptop_id = rec.get("laptop_id")
            laptop = laptop_map.get(laptop_id)

            if not laptop:
                logger.warning(f"LLM referenced unknown laptop ID: {laptop_id}")
                continue

            recommendations.append(
                LaptopRecommendation(
                    laptop=laptop,
                    rank=rec.get("rank", len(recommendations) + 1),
                    pros=rec.get("pros", []),
                    cons=rec.get("cons", []),
                    verdict=rec.get("verdict", ""),
                    best_for=rec.get("best_for", ""),
                )
            )

            self.db.increment_view_count(laptop_id)

        return RecommendationResponse(
            query_summary=llm_response.get("query_summary", ""),
            recommendations=recommendations,
            market_insight=llm_response.get("market_insight"),
        )

    def _fallback_recommendations(
        self,
        candidates: list[LaptopDB],
        request: RecommendationRequest,
        limit: int,
    ) -> RecommendationResponse:
        """Simple fallback when LLM fails."""
        logger.info("Using fallback recommendation logic")

        def score(laptop: LaptopDB) -> float:
            s = 0.0
            if laptop.price_etb and request.budget_max:
                if laptop.price_etb <= request.budget_max:
                    s += 10
            if laptop.ram_gb:
                s += laptop.ram_gb / 4
            if laptop.storage_gb:
                s += laptop.storage_gb / 200
            return s

        sorted_laptops = sorted(candidates, key=score, reverse=True)[:limit]

        recommendations = [
            LaptopRecommendation(
                laptop=laptop,
                rank=i + 1,
                pros=["Matches your criteria"],
                cons=["Unable to generate detailed analysis"],
                verdict=f"{laptop.brand} {laptop.model or 'laptop'}",
                best_for="General use",
            )
            for i, laptop in enumerate(sorted_laptops)
        ]

        return RecommendationResponse(
            query_summary="Based on your requirements",
            recommendations=recommendations,
            market_insight=None,
        )

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
