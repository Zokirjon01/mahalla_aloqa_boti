import asyncpg
from config import DATABASE_URL
from typing import Dict, List, Optional
from datetime import datetime

pool: asyncpg.Pool | None = None
user_menu_history: Dict[int, List[str]] = {}  # Foydalanuvchi menyu tarixi


async def init_db():
    """Ma'lumotlar bazasini ishga tushirish"""
    global pool
    try:
        print("🔄 Database ulanmoqda...")
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)

        async with pool.acquire() as conn:
            # Asosiy kontaklar jadvali
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                service TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                click_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """)

            # Click count uchun index
            await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_click_count 
            ON contacts(click_count DESC)
            """)

            # Mavjud ma'lumotlarni ko'rish
            count = await conn.fetchval("SELECT COUNT(*) FROM contacts")
            print(f"✅ Database ulandi. {count} ta kontakt mavjud")

        return True
    except Exception as e:
        print(f"❌ Database xatosi: {e}")
        return False


async def get_contacts():
    """Barcha kontaktlarni olish (faqat service va phone)"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT service, phone 
                FROM contacts 
                ORDER BY LOWER(service)
            """)

            result = [(r["service"], r["phone"]) for r in rows]
            return result
    except Exception as e:
        print(f"❌ Kontaktlarni olish xatosi: {e}")
        return []


async def get_contacts_with_clicks():
    """Barcha kontaktlarni click_count bilan olish (admin uchun)"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT service, phone, click_count
                FROM contacts 
                ORDER BY LOWER(service)
            """)

            result = [(r["service"], r["phone"], r["click_count"]) for r in rows]
            return result
    except Exception as e:
        print(f"❌ Kontaktlarni olish xatosi: {e}")
        return []


async def update_contact(service: str, phone: str):
    """Kontakt qo'shish yoki yangilash"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            # Oldin bor yoki yo'qligini tekshirish
            exists = await conn.fetchval(
                "SELECT 1 FROM contacts WHERE service = $1",
                service
            )

            if exists:
                # Yangilash
                await conn.execute("""
                    UPDATE contacts 
                    SET phone = $2, updated_at = NOW() 
                    WHERE service = $1
                """, service, phone)
                print(f"📝 Kontakt yangilandi: {service}")
            else:
                # Yangi qo'shish
                await conn.execute("""
                    INSERT INTO contacts (service, phone) 
                    VALUES ($1, $2)
                """, service, phone)
                print(f"➕ Yangi kontakt qo'shildi: {service}")

            return True

    except Exception as e:
        print(f"❌ Kontakt saqlash xatosi: {e}")
        return False


async def delete_contact(service: str):
    """Kontaktni o'chirish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM contacts WHERE service = $1",
                service
            )

            if "DELETE 1" in result:
                print(f"🗑️ Kontakt o'chirildi: {service}")
                return True
            else:
                print(f"⚠️ Kontakt topilmadi: {service}")
                return False
    except Exception as e:
        print(f"❌ Kontakt o'chirish xatosi: {e}")
        return False


async def increment_click_count(service: str):
    """Kontakt click sonini oshirish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE contacts 
                SET click_count = click_count + 1 
                WHERE service = $1
            """, service)
            return True
    except Exception as e:
        print(f"❌ Click count oshirish xatosi: {e}")
        return False


async def get_top_contacts(limit: int = 8):
    """Eng ko'p bosilgan kontaktlarni olish"""
    try:
        if not pool:
            await init_db()

        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT service, phone, click_count
                FROM contacts 
                WHERE click_count > 0
                ORDER BY click_count DESC
                LIMIT {limit}
            """)

            result = [(r["service"], r["phone"], r["click_count"]) for r in rows]
            return result
    except Exception as e:
        print(f"❌ Top kontaktlarni olish xatosi: {e}")
        return []


def add_to_menu_history(user_id: int, menu: str):
    """Foydalanuvchi menyu tarixiga qo'shish"""
    if user_id not in user_menu_history:
        user_menu_history[user_id] = []

    # Agar oxirgi menyu bir xil bo'lsa, qo'shmaymiz
    if not user_menu_history[user_id] or user_menu_history[user_id][-1] != menu:
        user_menu_history[user_id].append(menu)

    # Tarixni cheklash (masalan, oxirgi 10 ta)
    if len(user_menu_history[user_id]) > 10:
        user_menu_history[user_id] = user_menu_history[user_id][-10:]


def get_previous_menu(user_id: int) -> Optional[str]:
    """Oldingi menyuni olish"""
    if user_id in user_menu_history and len(user_menu_history[user_id]) > 1:
        # Joriy menyuni olib tashlaymiz
        user_menu_history[user_id].pop()
        # Oldingi menyuni qaytaramiz
        if user_menu_history[user_id]:
            return user_menu_history[user_id][-1]
    return None


def get_current_menu(user_id: int) -> Optional[str]:
    """Hozirgi menyuni olish"""
    if user_id in user_menu_history and user_menu_history[user_id]:
        return user_menu_history[user_id][-1]
    return None