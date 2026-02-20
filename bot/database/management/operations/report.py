import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ReportModel


async def create_ticket(session: AsyncSession, user_id: int, message: str) -> ReportModel:
    ticket = ReportModel(user_id=user_id, message=message)
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def get_oldest_unanswered(
    session: AsyncSession,
    skip_ids: list[uuid.UUID] | None = None
) -> ReportModel | None:
    q = (
        select(ReportModel)
        .where(ReportModel.admin_reply.is_(None))
        .order_by(ReportModel.created_at)
    )
    if skip_ids:
        q = q.where(ReportModel.id.not_in(skip_ids))
    result = await session.execute(q.limit(1))
    return result.scalar_one_or_none()


async def set_reply(
    session: AsyncSession,
    ticket_id: uuid.UUID,
    reply: str
) -> ReportModel | None:
    result = await session.execute(
        select(ReportModel).where(ReportModel.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        return None
    ticket.admin_reply = reply
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def count_unanswered(session: AsyncSession) -> int:
    result = await session.execute(
        select(ReportModel).where(ReportModel.admin_reply.is_(None))
    )
    return len(result.scalars().all())
