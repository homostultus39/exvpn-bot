from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class BotUser(BaseModel):
    telegram_id: int
    client_id: UUID
    agreed_to_terms: bool
    agreement_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
