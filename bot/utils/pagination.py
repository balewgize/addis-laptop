"""Pagination state management."""

from dataclasses import dataclass, field

from bot.constants import ITEMS_PER_PAGE


@dataclass
class PaginationState:
    """Track pagination state for a user."""

    command: str  # "browse" or "search"
    page: int = 1
    total_items: int = 0
    filters: dict = field(default_factory=dict)

    @property
    def total_pages(self) -> int:
        return max(1, (self.total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * ITEMS_PER_PAGE

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1
