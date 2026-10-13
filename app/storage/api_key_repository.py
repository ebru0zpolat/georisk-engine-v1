"""Persistence for hashed API keys (``api_keys`` table)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_api_key_id
from app.db.models import ApiKeyModel


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        organisation_id: str,
        label: str = "",
        scopes: list[str],
        key_hash: str,
        expires_at: datetime | None = None,
    ) -> ApiKeyModel:
        model = ApiKeyModel(
            id=new_api_key_id(),
            organisation_id=organisation_id,
            key_hash=key_hash,
            label=label,
            scopes=list(scopes),
            expires_at=expires_at,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_by_hash(self, key_hash: str) -> ApiKeyModel | None:
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def get(self, key_id: str) -> ApiKeyModel | None:
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.id == key_id)
        )
        return result.scalar_one_or_none()

    async def list_for_organisation(self, organisation_id: str) -> list[ApiKeyModel]:
        result = await self.session.execute(
            select(ApiKeyModel)
            .where(ApiKeyModel.organisation_id == organisation_id)
            .order_by(ApiKeyModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_used(self, key: ApiKeyModel, *, when: datetime) -> None:
        key.last_used_at = when
