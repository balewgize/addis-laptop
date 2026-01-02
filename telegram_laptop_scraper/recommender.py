"""Simple recommendation engine based on filtering and scoring."""

import logging

from .database import Database
from .schemas import LaptopDB, RecommendationQuery, SearchFilters

logger = logging.getLogger(__name__)


class Recommender:
    """Recommends laptops based on user criteria."""

    USE_CASE_PROFILES = {
        "programming": {"min_ram": 16, "min_storage": 512},
        "gaming": {"min_ram": 16, "min_storage": 512},
        "office": {"min_ram": 8, "min_storage": 256},
        "general": {"min_ram": 8, "min_storage": 256},
    }

    def __init__(self, database: Database | None = None):
        self.db = database or Database()

    def recommend(
        self,
        query: RecommendationQuery,
        limit: int = 10,
    ) -> list[LaptopDB]:
        """
        Get laptop recommendations based on user query.

        Args:
            query: User requirements
            limit: Maximum number of results

        Returns:
            List of laptops sorted by relevance score
        """
        logger.info(f"Getting recommendations for: {query.model_dump()}")

        # Build filters from query
        filters = SearchFilters(
            brand=query.brand,
            max_price=query.budget_max,
            min_ram=query.min_ram,
            min_storage=query.min_storage,
        )

        # Apply use case profile if specified
        if query.use_case and query.use_case in self.USE_CASE_PROFILES:
            profile = self.USE_CASE_PROFILES[query.use_case]
            if filters.min_ram is None:
                filters.min_ram = profile["min_ram"]
            if filters.min_storage is None:
                filters.min_storage = profile["min_storage"]
            logger.debug(f"Applied {query.use_case} profile: {profile}")

        # Get filtered results
        laptops = self.db.search(filters)
        logger.info(f"Found {len(laptops)} laptops matching filters")

        # Score and sort
        scored = [(laptop, self._score(laptop, query)) for laptop in laptops]
        scored.sort(key=lambda x: x[1], reverse=True)

        results = [laptop for laptop, score in scored[:limit]]
        logger.info(f"Returning top {len(results)} recommendations")

        return results

    def _score(self, laptop: LaptopDB, query: RecommendationQuery) -> float:
        """
        Score a laptop based on how well it matches the query.

        Higher score = better match.
        """
        score = 0.0

        # Prefer laptops with complete information
        if laptop.price_etb is not None:
            score += 10
        if laptop.ram_gb is not None:
            score += 5
        if laptop.storage_gb is not None:
            score += 5
        if laptop.cpu is not None:
            score += 3

        # Value scoring
        if laptop.ram_gb:
            score += min(laptop.ram_gb / 4, 10)
        if laptop.storage_gb:
            score += min(laptop.storage_gb / 100, 10)

        # Budget efficiency
        if query.budget_max and laptop.price_etb:
            budget_usage = laptop.price_etb / query.budget_max
            if budget_usage <= 1.0:
                if 0.7 <= budget_usage <= 0.9:
                    score += 15
                elif budget_usage < 0.7:
                    score += 10
                else:
                    score += 12

        return score
