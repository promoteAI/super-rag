from sqlalchemy import desc, func, select

from super_rag.db.models import (
    Role,
    User,
)
from super_rag.db.repositories.base import AsyncRepositoryProtocol


class AsyncUserRepositoryMixin(AsyncRepositoryProtocol):
    async def query_user_by_username(self, username: str):
        async def _query(session):
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self._execute_query(_query)

    async def query_user_by_email(self, email: str):
        async def _query(session):
            stmt = select(User).where(User.email == email)
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self._execute_query(_query)

    async def query_user_by_id(self, user_id: str):
        async def _query(session):
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self._execute_query(_query)

    async def query_user_exists(self, username: str = None, email: str = None):
        async def _query(session):
            stmt = select(User)
            if username:
                stmt = stmt.where(User.username == username)
            if email:
                stmt = stmt.where(User.email == email)
            result = await session.execute(stmt)
            return result.scalars().first() is not None

        return await self._execute_query(_query)

    async def create_user(self, username: str, email: str, password: str, role: Role):
        async def _operation(session):
            user = User(username=username, email=email, password=password, role=role)
            session.add(user)
            await session.flush()
            await session.refresh(user)
            return user

        return await self.execute_with_transaction(_operation)

    async def delete_user(self, user: User):
        async def _operation(session):
            await session.delete(user)
            await session.flush()

        return await self.execute_with_transaction(_operation)

    async def query_admin_count(self):
        async def _query(session):
            stmt = select(func.count()).select_from(User).where(User.role == Role.ADMIN, User.gmt_deleted.is_(None))
            return await session.scalar(stmt)

        return await self._execute_query(_query)

    async def query_user_count(self):
        async def _query(session):
            stmt = select(func.count()).select_from(User).where(User.gmt_deleted.is_(None))
            return await session.scalar(stmt)

        return await self._execute_query(_query)

    async def query_first_user_exists(self):
        async def _query(session):
            stmt = select(User).where(User.gmt_deleted.is_(None))
            result = await session.execute(stmt)
            return result.scalars().first() is not None

        return await self._execute_query(_query)
