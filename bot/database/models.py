import uuid
from datetime import datetime
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import func, BigInteger, Text, DateTime, UUID, Boolean, Integer, String

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


class TelegramAdminModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "telegram_admins"

    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)


class ReportModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reports"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)


class PendingPaymentModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pending_payments"

    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tariff_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_extension: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)  # "rukassa" | "yookassa"
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
