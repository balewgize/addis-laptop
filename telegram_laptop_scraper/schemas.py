"""Pydantic models for data validation and serialization."""

from datetime import datetime

from pydantic import BaseModel


class LaptopCreate(BaseModel):
    """Schema for LLM extraction output (without source fields)."""

    brand: str
    model: str | None = None
    cpu: str | None = None
    ram_gb: int | None = None
    storage_gb: int | None = None
    storage_type: str | None = None
    screen_size: float | None = None
    gpu: str | None = None
    price_etb: float | None = None
    condition: str | None = None
    contact: str | None = None


class Laptop(LaptopCreate):
    """Structured laptop data extracted from messages."""

    channel: str
    message_id: int
    posted_at: datetime
    raw_text: str


class LaptopDB(Laptop):
    """Laptop with database ID."""

    id: int


class SearchFilters(BaseModel):
    """Filters for laptop search."""

    brand: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_ram: int | None = None
    min_storage: int | None = None
    condition: str | None = None


class RecommendationQuery(BaseModel):
    """User query for recommendations."""

    budget_max: float | None = None
    min_ram: int | None = None
    min_storage: int | None = None
    brand: str | None = None
    use_case: str | None = None  # "programming", "gaming", "office", "general"


class ChannelSyncStatus(BaseModel):
    """Track when a channel was last synced."""

    channel: str
    last_synced: datetime
    message_count: int
    laptop_count: int


class SyncResult(BaseModel):
    """Result of a sync operation."""

    channel: str
    messages_fetched: int
    laptops_extracted: int
    errors: int
    skipped: int
