from sqlalchemy import select, delete
from db import Session, User, Memory, Knowledge, Usage

async def ensure_user(tg_id: int) -> User:
    async with Session() as s:
        user = (await s.execute(select(User).where(User.telegram_id == tg_id))).scalar_one_or_none()
        if not user:
            user = User(telegram_id=tg_id)
            s.add(user)
            await s.commit()
            await s.refresh(user)
        return user

async def add_memory(tg_id: int, content: str, category="general", confidence=0.8):
    async with Session() as s:
        s.add(Memory(user_id=tg_id, content=content, category=category, confidence=confidence))
        await s.commit()

async def get_memories(tg_id: int, limit=20):
    async with Session() as s:
        rows = (await s.execute(
            select(Memory).where(Memory.user_id == tg_id).order_by(Memory.id.desc()).limit(limit)
        )).scalars().all()
        return rows

async def clear_memories(tg_id: int):
    async with Session() as s:
        await s.execute(delete(Memory).where(Memory.user_id == tg_id))
        await s.commit()

async def add_knowledge(content: str, category="general", confidence=0.5, source_user_id=None, approved=False):
    async with Session() as s:
        s.add(Knowledge(content=content, category=category, confidence=confidence,
                        source_user_id=source_user_id, approved=approved))
        await s.commit()

async def get_knowledge(limit=20):
    async with Session() as s:
        return (await s.execute(
            select(Knowledge).where(Knowledge.approved == True)
            .order_by(Knowledge.confidence.desc()).limit(limit)
        )).scalars().all()

async def log_usage(tg_id: int, action: str):
    async with Session() as s:
        s.add(Usage(user_id=tg_id, action=action))
        await s.commit()
