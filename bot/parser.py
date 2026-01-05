"""LLM-based natural language query parser."""

import json
import logging
from dataclasses import dataclass

import httpx

from core.config import Settings, get_settings
from core.schemas import RecommendationRequest, SearchFilters
from core.utils import parse_json_from_llm

logger = logging.getLogger(__name__)

QUERY_PARSER_PROMPT = """Extract laptop search parameters from this query.

Return JSON with these fields (use null if not mentioned):
- brand: string or null (Dell, HP, Asus, Lenovo, Apple, etc.)
- max_price: number or null (in ETB - Ethiopian Birr)
- min_ram: number or null (in GB: 8, 16, 32)
- min_screen: number or null (in inches: 13, 14, 15, 17)
- use_case: string or null (programming, gaming, office, student, video_editing, general)

Examples:
- "Dell under 100k" → {{"brand": "Dell", "max_price": 100000}}
- "Gaming laptop 16GB RAM" → {{"use_case": "gaming", "min_ram": 16}}
- "15 inch laptop for programming" → {{"min_screen": 15, "use_case": "programming"}}

Query: {query}

JSON only:"""


@dataclass
class ParsedQuery:
    """Parsed search parameters from natural language."""

    brand: str | None = None
    max_price: float | None = None
    min_ram: int | None = None
    min_screen: float | None = None
    use_case: str | None = None
    raw_query: str = ""

    def to_search_filters(self) -> SearchFilters:
        """Convert to SearchFilters for database query."""
        return SearchFilters(
            brand=self.brand,
            max_price=self.max_price,
            min_ram=self.min_ram,
            min_screen=self.min_screen,
        )

    def to_recommendation_request(self) -> RecommendationRequest:
        """Convert to RecommendationRequest."""
        return RecommendationRequest(
            use_case=self.use_case,
            budget_max=self.max_price,
            min_ram=self.min_ram,
            min_screen=self.min_screen,
            brand_preference=self.brand,
        )

    def summary(self) -> str:
        """Human-readable summary of filters."""
        parts = []
        if self.brand:
            parts.append(f"Brand: {self.brand}")
        if self.max_price:
            parts.append(f"Under {self.max_price:,.0f} ETB")
        if self.min_ram:
            parts.append(f"{self.min_ram}GB+ RAM")
        if self.min_screen:
            parts.append(f'{self.min_screen}"+ screen')
        if self.use_case:
            parts.append(f"For {self.use_case}")

        return " • ".join(parts) if parts else "All laptops"


class QueryParser:
    """Parse natural language queries using LLM."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def parse(self, query: str) -> ParsedQuery:
        """Parse a natural language query into structured filters."""
        logger.info(f"Parsing query: {query}")

        try:
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": self.settings.llm_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": QUERY_PARSER_PROMPT.format(query=query),
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"]
            parsed_data = parse_json_from_llm(content)

            if parsed_data:
                result = ParsedQuery(
                    brand=parsed_data.get("brand"),
                    max_price=parsed_data.get("max_price"),
                    min_ram=parsed_data.get("min_ram"),
                    min_screen=parsed_data.get("min_screen"),
                    use_case=parsed_data.get("use_case"),
                    raw_query=query,
                )
                logger.info(f"Parsed: {result.summary()}")
                return result

        except Exception as e:
            logger.exception("Query parsing failed")

        return ParsedQuery(raw_query=query)

    def close(self):
        """Close the HTTP client."""
        self.client.close()
