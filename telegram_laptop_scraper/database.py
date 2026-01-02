"""SQLite database operations using SQLModel."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select, func

from .config import Settings, get_settings
from .schemas import Laptop, LaptopDB, SearchFilters, ChannelSyncStatus

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
    contact: str | None = None

    # Source tracking
    channel: str = Field(index=True)
    message_id: int
    posted_at: datetime = Field(index=True)
    raw_text: str

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChannelSyncModel(SQLModel, table=True):
    """Track channel sync history."""

    __tablename__ = "channel_syncs"

    id: int | None = Field(default=None, primary_key=True)
    channel: str = Field(unique=True, index=True)
    last_synced: datetime
    message_count: int = 0
    laptop_count: int = 0


class Database:
    """Database operations for laptops."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

        # Ensure data directory exists
        db_path = Path(self.settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(
            self.settings.database_url,
            echo=False,
        )
        SQLModel.metadata.create_all(self.engine)
        logger.info(f"Database initialized at {self.settings.database_path}")

    def add(self, laptop: Laptop) -> LaptopDB:
        """Add a laptop to the database."""
        with Session(self.engine) as session:
            db_laptop = LaptopModel(**laptop.model_dump())
            session.add(db_laptop)
            session.commit()
            session.refresh(db_laptop)
            logger.debug(
                f"Added laptop ID {db_laptop.id}: {laptop.brand} {laptop.model}"
            )
            return LaptopDB(**db_laptop.model_dump())

    def exists(self, channel: str, message_id: int) -> bool:
        """Check if a laptop from this message already exists."""
        with Session(self.engine) as session:
            statement = select(LaptopModel).where(
                LaptopModel.channel == channel,
                LaptopModel.message_id == message_id,
            )
            result = session.exec(statement).first()
            return result is not None

    def get_by_id(self, laptop_id: int) -> LaptopDB | None:
        """Get a laptop by ID."""
        with Session(self.engine) as session:
            laptop = session.get(LaptopModel, laptop_id)
            if laptop:
                return LaptopDB(**laptop.model_dump())
            return None

    def get_all(self, limit: int = 100, offset: int = 0) -> list[LaptopDB]:
        """Get all laptops with pagination."""
        with Session(self.engine) as session:
            statement = (
                select(LaptopModel)
                .order_by(LaptopModel.posted_at.desc())
                .offset(offset)
                .limit(limit)
            )
            results = session.exec(statement).all()
            return [LaptopDB(**r.model_dump()) for r in results]

    def get_by_channel(self, channel: str) -> list[LaptopDB]:
        """Get all laptops from a specific channel."""
        with Session(self.engine) as session:
            statement = (
                select(LaptopModel)
                .where(LaptopModel.channel == channel)
                .order_by(LaptopModel.posted_at.desc())
            )
            results = session.exec(statement).all()
            return [LaptopDB(**r.model_dump()) for r in results]

    def search(self, filters: SearchFilters) -> list[LaptopDB]:
        """Search laptops with filters."""
        with Session(self.engine) as session:
            statement = select(LaptopModel)

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

            statement = statement.order_by(LaptopModel.posted_at.desc())
            results = session.exec(statement).all()
            logger.debug(f"Search returned {len(results)} results")
            return [LaptopDB(**r.model_dump()) for r in results]

    def get_latest_message_id(self, channel: str) -> int:
        """Get the latest message ID for a channel (for incremental sync)."""
        with Session(self.engine) as session:
            statement = (
                select(LaptopModel.message_id)
                .where(LaptopModel.channel == channel)
                .order_by(LaptopModel.message_id.desc())
                .limit(1)
            )
            result = session.exec(statement).first()
            return result or 0

    def count(self) -> int:
        """Get total laptop count."""
        with Session(self.engine) as session:
            statement = select(func.count(LaptopModel.id))
            return session.exec(statement).one()

    def count_by_channel(self, channel: str) -> int:
        """Get laptop count for a specific channel."""
        with Session(self.engine) as session:
            statement = select(func.count(LaptopModel.id)).where(
                LaptopModel.channel == channel
            )
            return session.exec(statement).one()

    # Channel sync tracking

    def get_channel_sync_status(self, channel: str) -> ChannelSyncStatus | None:
        """Get the last sync status for a channel."""
        with Session(self.engine) as session:
            statement = select(ChannelSyncModel).where(
                ChannelSyncModel.channel == channel
            )
            result = session.exec(statement).first()
            if result:
                return ChannelSyncStatus(**result.model_dump())
            return None

    def update_channel_sync(
        self,
        channel: str,
        message_count: int,
        laptop_count: int,
    ):
        """Update or create channel sync record."""
        with Session(self.engine) as session:
            statement = select(ChannelSyncModel).where(
                ChannelSyncModel.channel == channel
            )
            existing = session.exec(statement).first()

            if existing:
                existing.last_synced = datetime.utcnow()
                existing.message_count = message_count
                existing.laptop_count = laptop_count
            else:
                sync_record = ChannelSyncModel(
                    channel=channel,
                    last_synced=datetime.utcnow(),
                    message_count=message_count,
                    laptop_count=laptop_count,
                )
                session.add(sync_record)

            session.commit()
            logger.info(f"Updated sync status for {channel}")

    def should_sync_channel(self, channel: str, cooldown_days: int = 7) -> bool:
        """Check if a channel should be synced based on cooldown period."""
        status = self.get_channel_sync_status(channel)

        if status is None:
            logger.debug(f"Channel {channel} has never been synced")
            return True

        cooldown = timedelta(days=cooldown_days)
        time_since_sync = datetime.utcnow() - status.last_synced

        should_sync = time_since_sync >= cooldown
        logger.debug(
            f"Channel {channel} last synced {time_since_sync.days} days ago. "
            f"Should sync: {should_sync}"
        )
        return should_sync

    def get_all_channel_statuses(self) -> list[ChannelSyncStatus]:
        """Get sync status for all channels."""
        with Session(self.engine) as session:
            statement = select(ChannelSyncModel).order_by(
                ChannelSyncModel.last_synced.desc()
            )
            results = session.exec(statement).all()
            return [ChannelSyncStatus(**r.model_dump()) for r in results]
