"""Pydantic models for data validation and serialization."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ListingTier(str, Enum):
    """Listing visibility tier for monetization."""

    FREE = "free"
    FEATURED = "featured"
    PREMIUM = "premium"


class SyncFrequency(str, Enum):
    """How often to sync a channel."""

    DAILY = "daily"
    EVERY_3_DAYS = "every_3_days"
    WEEKLY = "weekly"
    MANUAL = "manual"


# Extraction schemas


class LaptopCreate(BaseModel):
    """Schema for LLM extraction output."""

    brand: str
    model: str | None = None
    cpu: str | None = None
    ram_gb: int | None = None
    storage_gb: int | None = None
    storage_type: str | None = None
    screen_size: float | None = None
    gpu: str | None = None
    price_etb: float | None = None
    battery_life: str | None = None
    condition: str | None = None
    contact: str | None = None


class Laptop(LaptopCreate):
    """Structured laptop data with source tracking."""

    channel: str
    message_id: int
    posted_at: datetime
    raw_text: str


class LaptopDB(Laptop):
    """Laptop with database fields."""

    id: int
    created_at: datetime
    tier: ListingTier = ListingTier.FREE
    view_count: int = 0
    click_count: int = 0
    is_active: bool = True


# Recommendation schemas


class LaptopRecommendation(BaseModel):
    """LLM-generated recommendation with reasoning."""

    laptop: LaptopDB
    rank: int
    pros: list[str]
    cons: list[str]
    best_for: str


class RecommendationRequest(BaseModel):
    """User's recommendation request."""

    budget_max: float | None = None
    # budget_min: float | None = None
    min_ram: int | None = None
    min_screen: float | None = None
    use_case: str | None = None
    priorities: list[str] = Field(default_factory=list)
    brand_preference: str | None = None


class RecommendationResponse(BaseModel):
    """Full recommendation response."""

    query_summary: str
    recommendations: list[LaptopRecommendation]
    market_insight: str | None = None


# Channel management schemas


class ChannelConfig(BaseModel):
    """Configuration for a tracked channel."""

    channel: str
    name: str  # Display name
    sync_frequency: SyncFrequency = SyncFrequency.WEEKLY
    is_active: bool = True
    last_synced: datetime | None = None
    last_message_id: int = 0
    total_messages: int = 0
    total_laptops: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChannelConfigDB(ChannelConfig):
    """Channel config with database ID."""

    id: int


class SyncResult(BaseModel):
    """Result of a sync operation."""

    channel: str
    messages_fetched: int
    laptops_extracted: int
    errors: int
    skipped: int
    duration_seconds: float


class SearchFilters(BaseModel):
    """Filters for laptop search."""

    brand: str | None = None
    # min_price: float | None = None
    max_price: float | None = None
    min_ram: int | None = None
    min_screen: float | None = None
    min_storage: int | None = None
    condition: str | None = None
    channel: str | None = None
    posted_within_days: int | None = None


# Analytics schemas


class ChannelStats(BaseModel):
    """Stats for a channel."""

    channel: str
    name: str
    total_listings: int
    active_listings: int
    total_views: int
    total_clicks: int
    avg_price: float | None
    last_synced: datetime | None


class DashboardStats(BaseModel):
    """Overall dashboard statistics."""

    total_laptops: int
    total_channels: int
    total_views: int
    total_clicks: int
    laptops_last_7_days: int
    top_brands: list[tuple[str, int]]
