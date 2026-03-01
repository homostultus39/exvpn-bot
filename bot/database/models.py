import enum
import uuid
from datetime import datetime
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import func, BigInteger, Text, DateTime, UUID, Boolean, Integer, String, ForeignKey, LargeBinary

from bot.database.base import Base


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class SubscriptionStatus(enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    UNLIMITED = "unlimited"

class UserModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    aggreed_to_terms: Mapped[bool] = mapped_column(nullable=True, default=False)
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(String(50), default=SubscriptionStatus.EXPIRED.value, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    peers: Mapped[list["PeerModel"]] = relationship(
        "PeerModel",
        back_populates="client",
        cascade="all, delete-orphan",
        uselist=True,
    )


class PeerModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "peers"

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clusters.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)

    client: Mapped["UserModel"] = relationship("UserModel", back_populates="peers")
    cluster: Mapped["ClusterModel"] = relationship("ClusterModel", back_populates="peers")


class ClusterModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "clusters"

    endpoint: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    public_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)

    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    peers: Mapped["PeerModel"] = relationship("PeerModel", back_populates="cluster", cascade="all, delete-orphan", uselist=True)


class TariffModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tariffs"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    days: Mapped[int] = mapped_column(nullable=False)
    price_rub: Mapped[int | None] = mapped_column(nullable=True, default=None)
    price_stars: Mapped[int | None] = mapped_column(nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0, index=True)


class ReportModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reports"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)


class PendingPaymentModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pending_payments"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tariff_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_extension: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)