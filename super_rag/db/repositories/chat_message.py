from typing import List, Optional

from sqlalchemy import select, update
from super_rag.db.models import ChatMessageTable
from super_rag.utils.utils import utc_now

from super_rag.db.repositories.base import (
    AsyncRepositoryProtocol,
    SyncRepositoryProtocol,
)

class ChatMessageRepositoryMixin(SyncRepositoryProtocol):
    """
    Sync repository mixin for ChatMessageTable.
    """

    def get_messages(self, chat_id: str) -> List[ChatMessageTable]:
        """
        Get all messages in a chat, ordered by created_at (asc), filtering out soft-deleted ones.
        """
        def _query(session):
            stmt = (
                select(ChatMessageTable)
                .where(ChatMessageTable.chat_id == chat_id, ChatMessageTable.gmt_deleted.is_(None))
                .order_by(ChatMessageTable.created_at.asc())
            )
            result = session.execute(stmt)
            return result.scalars().all()
        return self._execute_query(_query)

    def get_message_by_id(self, message_id: str) -> Optional[ChatMessageTable]:
        """
        Get a chat message by its message_id, ignoring soft-deleted ones.
        """
        def _query(session):
            stmt = select(ChatMessageTable).where(
                ChatMessageTable.message_id == message_id,
                ChatMessageTable.gmt_deleted.is_(None)
            )
            result = session.execute(stmt)
            return result.scalars().first()
        return self._execute_query(_query)

    def insert_message(
        self,
        chat_id: str,
        role: str,
        raw_message: str,
        message_id: str = None,
    ) -> ChatMessageTable:
        """
        Insert a new chat message.

        Args:
            chat_id: Chat ID.
            role: Message role ("human", "ai", etc).
            raw_message: Raw JSON or text of the message.
            message_id: Optional unique message identifier.

        Returns:
            The inserted ChatMessageTable object.
        """
        def _op(session):
            chat_msg = ChatMessageTable(
                message_id=message_id,
                chat_id=chat_id,
                role=role,
                raw_message=raw_message,
            )
            session.add(chat_msg)
            session.flush()
            session.refresh(chat_msg)
            return chat_msg
        return self.execute_with_transaction(_op)

    def soft_delete_messages_by_chat(self, chat_id: str) -> int:
        """
        Soft delete (set gmt_deleted) all messages for a given chat_id.
        Returns the number of rows updated.
        """
        def _op(session):
            stmt = (
                update(ChatMessageTable)
                .where(ChatMessageTable.chat_id == chat_id, ChatMessageTable.gmt_deleted.is_(None))
                .values(gmt_deleted=utc_now())
            )
            result = session.execute(stmt)
            session.flush()
            return result.rowcount
        return self.execute_with_transaction(_op)

    def soft_delete_message_by_id(self, message_id: str) -> int:
        """
        Soft delete (set gmt_deleted) a single chat message by message_id.
        Returns the number of rows updated.
        """
        def _op(session):
            stmt = (
                update(ChatMessageTable)
                .where(ChatMessageTable.message_id == message_id, ChatMessageTable.gmt_deleted.is_(None))
                .values(gmt_deleted=utc_now())
            )
            result = session.execute(stmt)
            session.flush()
            return result.rowcount
        return self.execute_with_transaction(_op)

    def update_message_raw(self, message_id: str, raw_message: str) -> Optional[ChatMessageTable]:
        """
        Update the raw_message field of a message.
        Returns the updated message.
        """
        def _op(session):
            stmt = select(ChatMessageTable).where(
                ChatMessageTable.message_id == message_id,
                ChatMessageTable.gmt_deleted.is_(None)
            )
            result = session.execute(stmt)
            chat_msg = result.scalars().first()
            if chat_msg:
                chat_msg.raw_message = raw_message
                chat_msg.gmt_deleted = None
                session.add(chat_msg)
                session.flush()
                session.refresh(chat_msg)
                return chat_msg
            return None
        return self.execute_with_transaction(_op)


class AsyncChatMessageRepositoryMixin(AsyncRepositoryProtocol):
    """
    Async repository mixin for ChatMessageTable, following the AsyncLlmProviderRepositoryMixin pattern.
    """

    async def get_messages(self, chat_id: str) -> List[ChatMessageTable]:
        """
        Get all messages in a chat, ordered by created_at (asc), filtering out soft-deleted ones.
        """
        async def _query(session):
            stmt = (
                select(ChatMessageTable)
                .where(ChatMessageTable.chat_id == chat_id, ChatMessageTable.gmt_deleted.is_(None))
                .order_by(ChatMessageTable.created_at.asc())
            )
            result = await session.execute(stmt)
            return result.scalars().all()
        return await self._execute_query(_query)

    async def get_message_by_id(self, message_id: str) -> Optional[ChatMessageTable]:
        """
        Get a chat message by its message_id, ignoring soft-deleted ones.
        """
        async def _query(session):
            stmt = select(ChatMessageTable).where(
                ChatMessageTable.message_id == message_id,
                ChatMessageTable.gmt_deleted.is_(None)
            )
            result = await session.execute(stmt)
            return result.scalars().first()
        return await self._execute_query(_query)

    async def insert_message(
        self,
        chat_id: str,
        role: str,
        raw_message: str,
        message_id: str = None,
    ) -> ChatMessageTable:
        """
        Insert a new chat message.

        Args:
            chat_id: Chat ID.
            role: Message role ("human", "ai", etc).
            raw_message: Raw JSON or text of the message.
            message_id: Optional unique message identifier.

        Returns:
            The inserted ChatMessageTable object.
        """
        async def _op(session):
            chat_msg = ChatMessageTable(
                message_id=message_id,
                chat_id=chat_id,
                role=role,
                raw_message=raw_message,
            )
            session.add(chat_msg)
            await session.flush()
            await session.refresh(chat_msg)
            return chat_msg
        return await self.execute_with_transaction(_op)

    async def soft_delete_messages_by_chat(self, chat_id: str) -> int:
        """
        Soft delete (set gmt_deleted) all messages for a given chat_id.
        Returns the number of rows updated.
        """
        async def _op(session):
            stmt = (
                update(ChatMessageTable)
                .where(ChatMessageTable.chat_id == chat_id, ChatMessageTable.gmt_deleted.is_(None))
                .values(gmt_deleted=utc_now())
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.rowcount
        return await self.execute_with_transaction(_op)

    async def soft_delete_message_by_id(self, message_id: str) -> int:
        """
        Soft delete (set gmt_deleted) a single chat message by message_id.
        Returns the number of rows updated.
        """
        async def _op(session):
            stmt = (
                update(ChatMessageTable)
                .where(ChatMessageTable.message_id == message_id, ChatMessageTable.gmt_deleted.is_(None))
                .values(gmt_deleted=utc_now())
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.rowcount
        return await self.execute_with_transaction(_op)

    async def update_message_raw(self, message_id: str, raw_message: str) -> Optional[ChatMessageTable]:
        """
        Update the raw_message field of a message.
        Returns the updated message.
        """
        async def _op(session):
            stmt = select(ChatMessageTable).where(
                ChatMessageTable.message_id == message_id,
                ChatMessageTable.gmt_deleted.is_(None)
            )
            result = await session.execute(stmt)
            chat_msg = result.scalars().first()
            if chat_msg:
                chat_msg.raw_message = raw_message
                chat_msg.gmt_deleted = None
                session.add(chat_msg)
                await session.flush()
                await session.refresh(chat_msg)
                return chat_msg
            return None
        return await self.execute_with_transaction(_op)
