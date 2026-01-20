import asyncpg
from config import DATABASE_URL
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Database obyekti
pool: asyncpg.Pool | None = None
user_menu_history: Dict[int, List[str]] = {}  # Foydalanuvchi menyu tarixi


async def init_db():
    """Ma'lumotlar bazasini ishga tushirish"""
    global pool
    try:
        if not DATABASE_URL:
            print("❌ DATABASE_URL topilmadi! .env.local faylida DATABASE_URL ni kiriting")
            return False

        print("🔄 PostgreSQL database ulanmoqda...")
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            timeout=60,
            command_timeout=60
        )

        async with pool.acquire() as conn:
            # Asosiy kontaklar jadvali
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                service TEXT NOT NULL,
                phone TEXT NOT NULL,
                click_count INTEGER DEFAULT 0,
                group_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(service, group_id)
            )
            """)

            # Foydalanuvchilar jadvali
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                username VARCHAR(255),
                language_code VARCHAR(10),
                is_bot BOOLEAN DEFAULT FALSE,
                is_premium BOOLEAN DEFAULT FALSE,
                chat_id BIGINT,
                chat_type VARCHAR(50),
                started_at TIMESTAMP DEFAULT NOW(),
                last_activity TIMESTAMP DEFAULT NOW(),
                message_count INTEGER DEFAULT 0,
                last_command TEXT,
                UNIQUE(user_id, chat_id)
            )
            """)

            # Indexlar
            await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_click_count 
            ON contacts(click_count DESC)
            """)

            await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_group_id 
            ON contacts(group_id)
            """)

            await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_user_id 
            ON users(user_id)
            """)

            contacts_count = await conn.fetchval("SELECT COUNT(*) FROM contacts")
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            print(f"✅ PostgreSQL database ulandi. {contacts_count} ta kontakt, {users_count} ta foydalanuvchi mavjud")

        return True
    except Exception as e:
        print(f"❌ Database xatosi: {e}")
        return False


async def save_user(
        user_id: int,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        language_code: str = None,
        is_bot: bool = False,
        is_premium: bool = False,
        chat_id: int = None,
        chat_type: str = None,
        command: str = None
) -> bool:
    """Foydalanuvchi ma'lumotlarini saqlash yoki yangilash"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users 
                (user_id, first_name, last_name, username, language_code, 
                 is_bot, is_premium, chat_id, chat_type, last_activity, message_count, last_command)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), 1, $10)
                ON CONFLICT (user_id, chat_id) 
                DO UPDATE SET
                    first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                    last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                    username = COALESCE(EXCLUDED.username, users.username),
                    language_code = COALESCE(EXCLUDED.language_code, users.language_code),
                    is_premium = EXCLUDED.is_premium,
                    chat_type = EXCLUDED.chat_type,
                    last_activity = NOW(),
                    last_command = EXCLUDED.last_command,
                    message_count = users.message_count + 1
            """, user_id, first_name, last_name, username, language_code,
                               is_bot, is_premium, chat_id, chat_type, command)

            return True
    except Exception as e:
        print(f"❌ Foydalanuvchi saqlash xatosi: {e}")
        return False


async def save_user_activity(user_id: int, chat_id: int = None, command: str = None):
    """Faqat faollikni yangilash"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            if command:
                await conn.execute("""
                    UPDATE users 
                    SET last_activity = NOW(), 
                        message_count = message_count + 1,
                        last_command = $3
                    WHERE user_id = $1 AND chat_id = $2
                """, user_id, chat_id, command)
            else:
                await conn.execute("""
                    UPDATE users 
                    SET last_activity = NOW(), 
                        message_count = message_count + 1
                    WHERE user_id = $1 AND chat_id = $2
                """, user_id, chat_id)
    except Exception as e:
        print(f"⚠️ Faollik yangilash xatosi: {e}")


async def get_user_stats(user_id: int, chat_id: int = None):
    """Foydalanuvchi statistikasini olish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            if chat_id:
                row = await conn.fetchrow("""
                    SELECT 
                        user_id, first_name, last_name, username, chat_id, chat_type,
                        started_at, last_activity, message_count, last_command
                    FROM users 
                    WHERE user_id = $1 AND chat_id = $2
                    ORDER BY last_activity DESC
                    LIMIT 1
                """, user_id, chat_id)
            else:
                row = await conn.fetchrow("""
                    SELECT 
                        user_id, first_name, last_name, username, chat_id, chat_type,
                        started_at, last_activity, message_count, last_command
                    FROM users 
                    WHERE user_id = $1
                    ORDER BY last_activity DESC
                    LIMIT 1
                """, user_id)

            if row:
                return dict(row)
            return None
    except Exception as e:
        print(f"❌ Foydalanuvchi statistikasi xatosi: {e}")
        return None


async def get_all_users(limit: int = 100):
    """Barcha foydalanuvchilarni olish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    user_id,
                    MAX(first_name) as first_name,
                    MAX(last_name) as last_name,
                    MAX(username) as username,
                    COUNT(DISTINCT chat_id) as total_chats,
                    MAX(last_activity) as last_seen,
                    SUM(message_count) as total_messages,
                    MAX(CASE WHEN chat_type = 'private' THEN 1 ELSE 0 END) as has_private
                FROM users 
                GROUP BY user_id
                ORDER BY last_seen DESC
                LIMIT $1
            """, limit)

            return [dict(r) for r in rows]
    except Exception as e:
        print(f"❌ Foydalanuvchilarni olish xatosi: {e}")
        return []


async def get_contacts(group_id: int) -> List[Tuple[str, str]]:
    """Barcha kontaktlarni olish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT service, phone 
                FROM contacts 
                WHERE group_id = $1
                ORDER BY LOWER(service)
            """, group_id)

            return [(r["service"], r["phone"]) for r in rows]
    except Exception as e:
        print(f"❌ Kontaktlarni olish xatosi: {e}")
        return []


async def get_contacts_with_clicks(group_id: int) -> List[Tuple[str, str, int]]:
    """Barcha kontaktlarni click_count bilan olish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT service, phone, click_count
                FROM contacts 
                WHERE group_id = $1
                ORDER BY LOWER(service)
            """, group_id)

            return [(r["service"], r["phone"], r["click_count"]) for r in rows]
    except Exception as e:
        print(f"❌ Kontaktlarni olish xatosi: {e}")
        return []


async def update_contact(service: str, phone: str, group_id: int) -> bool:
    """Kontakt qo'shish yoki yangilash"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM contacts WHERE service = $1 AND group_id = $2",
                service, group_id
            )

            if exists:
                await conn.execute("""
                    UPDATE contacts 
                    SET phone = $3, updated_at = NOW() 
                    WHERE service = $1 AND group_id = $2
                """, service, group_id, phone)
            else:
                await conn.execute("""
                    INSERT INTO contacts (service, phone, group_id) 
                    VALUES ($1, $2, $3)
                """, service, phone, group_id)
            return True
    except Exception as e:
        print(f"❌ Kontakt saqlash xatosi: {e}")
        return False


async def delete_contact(service: str, group_id: int) -> bool:
    """Kontaktni o'chirish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM contacts WHERE service = $1 AND group_id = $2",
                service, group_id
            )
            return "DELETE 1" in result
    except Exception as e:
        print(f"❌ Kontakt o'chirish xatosi: {e}")
        return False


async def increment_click_count(service: str, group_id: int) -> bool:
    """Kontakt click sonini oshirish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE contacts 
                SET click_count = click_count + 1 
                WHERE service = $1 AND group_id = $2
            """, service, group_id)
            return True
    except Exception as e:
        print(f"❌ Click count oshirish xatosi: {e}")
        return False


async def get_top_contacts(limit: int = 8, group_id: int = None) -> List[Tuple[str, str, int]]:
    """Eng ko'p bosilgan kontaktlarni olish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            if group_id is None:
                rows = await conn.fetch(f"""
                    SELECT service, phone, click_count
                    FROM contacts 
                    WHERE click_count > 0
                    ORDER BY click_count DESC
                    LIMIT $1
                """, limit)
            else:
                rows = await conn.fetch(f"""
                    SELECT service, phone, click_count
                    FROM contacts 
                    WHERE group_id = $1 AND click_count > 0
                    ORDER BY click_count DESC
                    LIMIT $2
                """, group_id, limit)

            return [(r["service"], r["phone"], r["click_count"]) for r in rows]
    except Exception as e:
        print(f"❌ Top kontaktlarni olish xatosi: {e}")
        return []


def add_to_menu_history(user_id: int, menu: str):
    """Foydalanuvchi menyu tarixiga qo'shish"""
    if user_id not in user_menu_history:
        user_menu_history[user_id] = []

    if not user_menu_history[user_id] or user_menu_history[user_id][-1] != menu:
        user_menu_history[user_id].append(menu)

    if len(user_menu_history[user_id]) > 10:
        user_menu_history[user_id] = user_menu_history[user_id][-10:]


def get_previous_menu(user_id: int) -> Optional[str]:
    """Oldingi menyuni olish"""
    if user_id in user_menu_history and len(user_menu_history[user_id]) > 1:
        user_menu_history[user_id].pop()
        if user_menu_history[user_id]:
            return user_menu_history[user_id][-1]
    return None


def get_current_menu(user_id: int) -> Optional[str]:
    """Hozirgi menyuni olish"""
    if user_id in user_menu_history and user_menu_history[user_id]:
        return user_menu_history[user_id][-1]
    return None


async def close_db():
    """Database ulanishini yopish"""
    try:
        if pool:
            await pool.close()
            print("✅ PostgreSQL pool yopildi.")
    except Exception as e:
        print(f"❌ Database yopish xatosi: {e}")