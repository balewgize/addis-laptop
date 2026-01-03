"""SQLite database operations using SQLModel."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select, func, col

from .config import Settings, get_settings
from .schemas import (
    Laptop,
    LaptopDB,
    SearchFilters,
    ChannelConfig,
    ChannelConfigDB,
    ChannelStats,
    DashboardStats,
    SyncFrequency,
    ListingTier,
)

logger = logging.getLogger(__name__)


class LaptopModel(SQLModel, table=True):
    """SQLite table model for laptops."""

    __tablename__ = "laptops"

    id: int | None = Field(default=None, primary_key=True)

    # Core specs
    brand: str = Field(index=True)
    model: str | None = None
    cpu: str | None = None
    ram_gb: int | None = Field(default=None, index=True)
    storage_gb: int | None = Field(default=None, index=True)
    storage_type: str | None = None
    screen_size: float | None = None
    gpu: str | None = None

    # Pricing & condition
    price_etb: float | None = Field(default=None, index=True)
    condition: str | None = None
    battery_life: str | None = None
    contact: str | None = None

    # Source tracking
    channel: str = Field(index=True)
    message_id: int
    posted_at: datetime = Field(index=True)
    raw_text: str

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Monetization
    tier: str = Field(default="free", index=True)
    view_count: int = Field(default=0)
    click_count: int = Field(default=0)
    is_active: bool = Field(default=True, index=True)


class ChannelConfigModel(SQLModel, table=True):
    """SQLite table for channel configuration."""

    __tablename__ = "channel_configs"

    id: int | None = Field(default=None, primary_key=True)
    channel: str = Field(unique=True, index=True)
    name: str
    sync_frequency: str = Field(default="weekly")
    is_active: bool = Field(default=True)
    last_synced: datetime | None = None
    last_message_id: int = Field(default=0)
    total_messages: int = Field(default=0)
    total_laptops: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Database:
    """Database operations for laptops and channels."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

        db_path = Path(self.settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(self.settings.database_url, echo=False)
        SQLModel.metadata.create_all(self.engine)
        logger.info(f"Database initialized at {self.settings.database_path}")

    # ==================== Laptop Operations ====================

    def add_laptop(self, laptop: Laptop) -> LaptopDB:
        """Add a laptop to the database."""
        with Session(self.engine) as session:
            db_laptop = LaptopModel(**laptop.model_dump())
            session.add(db_laptop)
            session.commit()
            session.refresh(db_laptop)
            logger.debug(
                f"Added laptop ID {db_laptop.id}: {laptop.brand} {laptop.model}"
            )
            return self._laptop_model_to_db(db_laptop)

    def laptop_exists(self, channel: str, message_id: int) -> bool:
        """Check if a laptop from this message already exists."""
        with Session(self.engine) as session:
            statement = select(LaptopModel).where(
                LaptopModel.channel == channel,
                LaptopModel.message_id == message_id,
            )
            return session.exec(statement).first() is not None

    def get_laptop_by_id(self, laptop_id: int) -> LaptopDB | None:
        """Get a laptop by ID."""
        with Session(self.engine) as session:
            laptop = session.get(LaptopModel, laptop_id)
            if laptop:
                return self._laptop_model_to_db(laptop)
            return None

    def get_laptops(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[LaptopDB]:
        """Get laptops with pagination."""
        with Session(self.engine) as session:
            statement = select(LaptopModel)

            if active_only:
                statement = statement.where(LaptopModel.is_active == True)

            statement = (
                statement.order_by(LaptopModel.posted_at.desc())
                .offset(offset)
                .limit(limit)
            )
            results = session.exec(statement).all()
            return [self._laptop_model_to_db(r) for r in results]

    def search_laptops(self, filters: SearchFilters) -> list[LaptopDB]:
        """Search laptops with filters."""
        with Session(self.engine) as session:
            statement = select(LaptopModel).where(LaptopModel.is_active == True)

            if filters.brand:
                statement = statement.where(
                    LaptopModel.brand.ilike(f"%{filters.brand}%")
                )
            if filters.min_price is not None:
                statement = statement.where(LaptopModel.price_etb >= filters.min_price)
            if filters.max_price is not None:
                statement = statement.where(LaptopModel.price_etb <= filters.max_price)
            if filters.min_ram is not None:
                statement = statement.where(LaptopModel.ram_gb >= filters.min_ram)
            if filters.min_storage is not None:
                statement = statement.where(
                    LaptopModel.storage_gb >= filters.min_storage
                )
            if filters.condition:
                statement = statement.where(LaptopModel.condition == filters.condition)
            if filters.channel:
                statement = statement.where(LaptopModel.channel == filters.channel)
            if filters.posted_within_days:
                cutoff = datetime.utcnow() - timedelta(days=filters.posted_within_days)
                statement = statement.where(LaptopModel.posted_at >= cutoff)

            statement = statement.order_by(LaptopModel.posted_at.desc())
            results = session.exec(statement).all()
            logger.debug(f"Search returned {len(results)} results")
            return [self._laptop_model_to_db(r) for r in results]

    def get_featured_laptops(self, limit: int = 5) -> list[LaptopDB]:
        """Get featured/premium listings."""
        with Session(self.engine) as session:
            statement = (
                select(LaptopModel)
                .where(LaptopModel.tier.in_(["featured", "premium"]))
                .where(LaptopModel.is_active == True)
                .order_by(LaptopModel.created_at.desc())
                .limit(limit)
            )
            results = session.exec(statement).all()
            return [self._laptop_model_to_db(r) for r in results]

    def increment_view_count(self, laptop_id: int):
        """Increment view count for analytics."""
        with Session(self.engine) as session:
            laptop = session.get(LaptopModel, laptop_id)
            if laptop:
                laptop.view_count += 1
                session.commit()

    def increment_click_count(self, laptop_id: int):
        """Increment click count for analytics."""
        with Session(self.engine) as session:
            laptop = session.get(LaptopModel, laptop_id)
            if laptop:
                laptop.click_count += 1
                session.commit()

    def set_laptop_tier(self, laptop_id: int, tier: ListingTier):
        """Update laptop tier for monetization."""
        with Session(self.engine) as session:
            laptop = session.get(LaptopModel, laptop_id)
            if laptop:
                laptop.tier = tier.value
                session.commit()
                logger.info(f"Updated laptop {laptop_id} to tier: {tier}")

    def set_laptop_active(self, laptop_id: int, is_active: bool):
        """Activate/deactivate a laptop listing."""
        with Session(self.engine) as session:
            laptop = session.get(LaptopModel, laptop_id)
            if laptop:
                laptop.is_active = is_active
                session.commit()

    def count_laptops(self, active_only: bool = True) -> int:
        """Get total laptop count."""
        with Session(self.engine) as session:
            statement = select(func.count(LaptopModel.id))
            if active_only:
                statement = statement.where(LaptopModel.is_active == True)
            return session.exec(statement).one()

    def count_laptops_by_channel(self, channel: str) -> int:
        """Get laptop count for a specific channel."""
        with Session(self.engine) as session:
            statement = select(func.count(LaptopModel.id)).where(
                LaptopModel.channel == channel,
                LaptopModel.is_active == True,
            )
            return session.exec(statement).one()

    # ==================== Channel Operations ====================

    def add_channel(self, config: ChannelConfig) -> ChannelConfigDB:
        """Add a new channel to track."""
        with Session(self.engine) as session:
            db_config = ChannelConfigModel(**config.model_dump())
            session.add(db_config)
            session.commit()
            session.refresh(db_config)
            logger.info(f"Added channel: {config.channel}")
            return self._channel_model_to_db(db_config)

    def get_channel(self, channel: str) -> ChannelConfigDB | None:
        """Get channel configuration."""
        with Session(self.engine) as session:
            statement = select(ChannelConfigModel).where(
                ChannelConfigModel.channel == channel
            )
            result = session.exec(statement).first()
            if result:
                return self._channel_model_to_db(result)
            return None

    def get_all_channels(self, active_only: bool = False) -> list[ChannelConfigDB]:
        """Get all tracked channels."""
        with Session(self.engine) as session:
            statement = select(ChannelConfigModel)
            if active_only:
                statement = statement.where(ChannelConfigModel.is_active == True)
            statement = statement.order_by(ChannelConfigModel.created_at.desc())
            results = session.exec(statement).all()
            return [self._channel_model_to_db(r) for r in results]

    def update_channel_sync(
        self,
        channel: str,
        last_message_id: int,
        messages_count: int,
        laptops_count: int,
    ):
        """Update channel after sync."""
        with Session(self.engine) as session:
            statement = select(ChannelConfigModel).where(
                ChannelConfigModel.channel == channel
            )
            config = session.exec(statement).first()
            if config:
                config.last_synced = datetime.utcnow()
                config.last_message_id = max(config.last_message_id, last_message_id)
                config.total_messages += messages_count
                config.total_laptops += laptops_count
                session.commit()
                logger.info(f"Updated sync status for {channel}")

    def update_channel_config(
        self,
        channel: str,
        name: str | None = None,
        sync_frequency: SyncFrequency | None = None,
        is_active: bool | None = None,
    ):
        """Update channel configuration."""
        with Session(self.engine) as session:
            statement = select(ChannelConfigModel).where(
                ChannelConfigModel.channel == channel
            )
            config = session.exec(statement).first()
            if config:
                if name is not None:
                    config.name = name
                if sync_frequency is not None:
                    config.sync_frequency = sync_frequency.value
                if is_active is not None:
                    config.is_active = is_active
                session.commit()
                logger.info(f"Updated config for {channel}")

    def delete_channel(self, channel: str):
        """Delete a channel and optionally its laptops."""
        with Session(self.engine) as session:
            # Delete channel config
            statement = select(ChannelConfigModel).where(
                ChannelConfigModel.channel == channel
            )
            config = session.exec(statement).first()
            if config:
                session.delete(config)
                session.commit()
                logger.info(f"Deleted channel: {channel}")

    def get_channels_to_sync(self) -> list[ChannelConfigDB]:
        """Get channels that need to be synced based on their frequency."""
        with Session(self.engine) as session:
            statement = select(ChannelConfigModel).where(
                ChannelConfigModel.is_active == True
            )
            results = session.exec(statement).all()

            channels_to_sync = []
            now = datetime.utcnow()

            for config in results:
                if config.sync_frequency == "manual":
                    continue

                if config.last_synced is None:
                    channels_to_sync.append(self._channel_model_to_db(config))
                    continue

                time_since_sync = now - config.last_synced

                should_sync = False
                if config.sync_frequency == "daily":
                    should_sync = time_since_sync >= timedelta(days=1)
                elif config.sync_frequency == "every_3_days":
                    should_sync = time_since_sync >= timedelta(days=3)
                elif config.sync_frequency == "weekly":
                    should_sync = time_since_sync >= timedelta(days=7)

                if should_sync:
                    channels_to_sync.append(self._channel_model_to_db(config))

            logger.info(f"Found {len(channels_to_sync)} channels to sync")
            return channels_to_sync

    # ==================== Analytics ====================

    def get_channel_stats(self, channel: str) -> ChannelStats | None:
        """Get statistics for a channel."""
        config = self.get_channel(channel)
        if not config:
            return None

        with Session(self.engine) as session:
            # Get laptop stats
            laptops = session.exec(
                select(LaptopModel).where(LaptopModel.channel == channel)
            ).all()

            if not laptops:
                return ChannelStats(
                    channel=channel,
                    name=config.name,
                    total_listings=0,
                    active_listings=0,
                    total_views=0,
                    total_clicks=0,
                    avg_price=None,
                    last_synced=config.last_synced,
                )

            active = [l for l in laptops if l.is_active]
            prices = [l.price_etb for l in active if l.price_etb]

            return ChannelStats(
                channel=channel,
                name=config.name,
                total_listings=len(laptops),
                active_listings=len(active),
                total_views=sum(l.view_count for l in laptops),
                total_clicks=sum(l.click_count for l in laptops),
                avg_price=sum(prices) / len(prices) if prices else None,
                last_synced=config.last_synced,
            )

    def get_dashboard_stats(self) -> DashboardStats:
        """Get overall dashboard statistics."""
        with Session(self.engine) as session:
            # Total counts
            total_laptops = session.exec(
                select(func.count(LaptopModel.id)).where(LaptopModel.is_active == True)
            ).one()

            total_channels = session.exec(
                select(func.count(ChannelConfigModel.id))
            ).one()

            # Views and clicks
            views_clicks = session.exec(
                select(
                    func.sum(LaptopModel.view_count),
                    func.sum(LaptopModel.click_count),
                )
            ).one()
            total_views = views_clicks[0] or 0
            total_clicks = views_clicks[1] or 0

            # Last 7 days
            week_ago = datetime.utcnow() - timedelta(days=7)
            laptops_last_7_days = session.exec(
                select(func.count(LaptopModel.id)).where(
                    LaptopModel.created_at >= week_ago,
                    LaptopModel.is_active == True,
                )
            ).one()

            # Top brands
            brand_counts = session.exec(
                select(LaptopModel.brand, func.count(LaptopModel.id))
                .where(LaptopModel.is_active == True)
                .group_by(LaptopModel.brand)
                .order_by(func.count(LaptopModel.id).desc())
                .limit(5)
            ).all()

            return DashboardStats(
                total_laptops=total_laptops,
                total_channels=total_channels,
                total_views=total_views,
                total_clicks=total_clicks,
                laptops_last_7_days=laptops_last_7_days,
                top_brands=list(brand_counts),
            )

    # ==================== Helpers ====================

    def _laptop_model_to_db(self, model: LaptopModel) -> LaptopDB:
        """Convert SQLModel to Pydantic schema."""
        return LaptopDB(
            id=model.id,
            brand=model.brand,
            model=model.model,
            cpu=model.cpu,
            ram_gb=model.ram_gb,
            storage_gb=model.storage_gb,
            storage_type=model.storage_type,
            screen_size=model.screen_size,
            gpu=model.gpu,
            price_etb=model.price_etb,
            battery_life=model.battery_life,
            condition=model.condition,
            contact=model.contact,
            channel=model.channel,
            message_id=model.message_id,
            posted_at=model.posted_at,
            raw_text=model.raw_text,
            created_at=model.created_at,
            tier=ListingTier(model.tier),
            view_count=model.view_count,
            click_count=model.click_count,
            is_active=model.is_active,
        )

    def _channel_model_to_db(self, model: ChannelConfigModel) -> ChannelConfigDB:
        """Convert SQLModel to Pydantic schema."""
        return ChannelConfigDB(
            id=model.id,
            channel=model.channel,
            name=model.name,
            sync_frequency=SyncFrequency(model.sync_frequency),
            is_active=model.is_active,
            last_synced=model.last_synced,
            last_message_id=model.last_message_id,
            total_messages=model.total_messages,
            total_laptops=model.total_laptops,
            created_at=model.created_at,
        )
