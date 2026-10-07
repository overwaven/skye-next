"""Access: who may talk to Skye.

Private chat is open to any non-banned user. A group is enabled only when the
owner allowlists it or a member volunteers to sponsor it; payment inside an
enabled chat is handled by :mod:`skye.sparks`.
"""

from __future__ import annotations

from .db import Database
from .models import RequestContext, Scope


class AccessService:
    def __init__(self, database: Database, owner_ids: frozenset[int]) -> None:
        self.database = database
        self.owner_ids = owner_ids

    def is_owner(self, user_id: int) -> bool:
        return user_id in self.owner_ids

    async def banned(self, user_id: int) -> bool:
        if self.is_owner(user_id):
            return False
        return await self.database.access_effect(Scope("user", user_id)) == "ban"

    async def allowed(self, context: RequestContext) -> bool:
        if self.is_owner(context.user_id):
            return True
        if await self.banned(context.user_id):
            return False
        if context.chat_type == "private":
            return True
        if await self.database.access_effect(context.scope) == "allow":
            return True
        return await self.database.chat_sponsor(context.chat_id) is not None
