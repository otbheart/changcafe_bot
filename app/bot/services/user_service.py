from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.models import User, UserRole
from infrastructure.logger import logger

class UserService:
    """Сервис для безопасного создания пользователей."""
    
    async def get_or_create_by_phone(
        self,
        session: AsyncSession,
        phone: str,
        name: str,
        email: str = None
    ) -> User:
        """Получить или создать пользователя по phone (защита от race condition)."""
        
        try:
            # Пытаемся найти
            from sqlalchemy import select
            stmt = select(User).where(User.phone == phone)
            result = await session.execute(stmt)
            user = result.scalars().first()
            
            if user:
                return user
            
            # Создаём нового
            import random
            temp_id = random.randint(10000000, 99999999)
            
            user = User(
                user_id=temp_id,
                first_name=name,
                phone=phone,
                email=email,
                role=UserRole.CLIENT
            )
            
            session.add(user)
            await session.flush()
            
            logger.info("user_created_from_tilda", phone=phone, name=name)
            return user
            
        except IntegrityError:
            # Другой поток создал пользователя одновременно
            await session.rollback()
            
            stmt = select(User).where(User.phone == phone)
            result = await session.execute(stmt)
            user = result.scalars().first()
            
            if user:
                logger.info("user_already_exists_after_race", phone=phone)
                return user
            
            raise
