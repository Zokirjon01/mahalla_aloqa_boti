import os
import asyncpg
import aiosqlite
from typing import Dict, List, Optional, Union
from datetime import datetime

# Database obyekti
pool: Union[asyncpg.Pool, None] = None
sqlite_conn: Union[aiosqlite.Connection, None] = None
user_menu_history: Dict[int, List[str]] = {}  # Foydalanuvchi menyu tarixi


def is_postgres():
    """PostgreSQL yoki SQLite ekanligini aniqlash"""
    db_url = os.getenv("DATABASE_URL", "").strip()
    return db_url.startswith("postgresql://")


async def init_db():
    """Ma'lumotlar bazasini ishga tushirish"""
    global pool, sqlite_conn

    try:
        if is_postgres():
            # PostgreSQL
            print("🔄 PostgreSQL database ulanmoqda...")
            db_url = os.getenv("DATABASE_URL")

            pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=5,
                timeout=30
            )

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
                print(f"✅ PostgreSQL database ulandi. {count} ta kontakt mavjud")

            return True
        else:
            # SQLite
            print("🔄 SQLite database ulanmoqda...")

            # SQLite fayl nomi
            db_path = os.getenv("SQLITE_DB_PATH", "mahalla.db")

            sqlite_conn = await aiosqlite.connect(db_path)

            # SQLite uchun jadval yaratish
            await sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                click_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Click count uchun index
            await sqlite_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_click_count 
            ON contacts(click_count DESC)
            """)

            await sqlite_conn.commit()

            # Mavjud ma'lumotlarni ko'rish
            async with sqlite_conn.execute("SELECT COUNT(*) FROM contacts") as cursor:
                count = await cursor.fetchone()
                print(f"✅ SQLite database ulandi. {count[0]} ta kontakt mavjud")

            return True

    except Exception as e:
        print(f"❌ Database xatosi: {e}")
        return False


async def get_contacts():
    """Barcha kontaktlarni olish (faqat service va phone)"""
    try:
        if is_postgres():
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
        else:
            # SQLite
            if not sqlite_conn:
                await init_db()

            async with sqlite_conn.execute("""
                SELECT service, phone 
                FROM contacts 
                ORDER BY LOWER(service)
            """) as cursor:
                rows = await cursor.fetchall()
                return [(row[0], row[1]) for row in rows]

    except Exception as e:
        print(f"❌ Kontaktlarni olish xatosi: {e}")
        return []


async def get_contacts_with_clicks():
    """Barcha kontaktlarni click_count bilan olish (admin uchun)"""
    try:
        if is_postgres():
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
        else:
            # SQLite
            if not sqlite_conn:
                await init_db()

            async with sqlite_conn.execute("""
                SELECT service, phone, click_count
                FROM contacts 
                ORDER BY LOWER(service)
            """) as cursor:
                rows = await cursor.fetchall()
                return [(row[0], row[1], row[2]) for row in rows]

    except Exception as e:
        print(f"❌ Kontaktlarni olish xatosi: {e}")
        return []


async def update_contact(service: str, phone: str):
    """Kontakt qo'shish yoki yangilash"""
    try:
        if is_postgres():
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
        else:
            # SQLite
            if not sqlite_conn:
                await init_db()

            # Bor yoki yo'qligini tekshirish
            async with sqlite_conn.execute(
                    "SELECT 1 FROM contacts WHERE service = ?",
                    (service,)
            ) as cursor:
                exists = await cursor.fetchone()

            if exists:
                # Yangilash
                await sqlite_conn.execute("""
                    UPDATE contacts 
                    SET phone = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE service = ?
                """, (phone, service))
                print(f"📝 Kontakt yangilandi: {service}")
            else:
                # Yangi qo'shish
                await sqlite_conn.execute("""
                    INSERT INTO contacts (service, phone) 
                    VALUES (?, ?)
                """, (service, phone))
                print(f"➕ Yangi kontakt qo'shildi: {service}")

            await sqlite_conn.commit()
            return True

    except Exception as e:
        print(f"❌ Kontakt saqlash xatosi: {e}")
        return False


async def delete_contact(service: str):
    """Kontaktni o'chirish"""
    try:
        if is_postgres():
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
        else:
            # SQLite
            if not sqlite_conn:
                await init_db()

            async with sqlite_conn.execute(
                    "DELETE FROM contacts WHERE service = ?",
                    (service,)
            ) as cursor:
                await sqlite_conn.commit()

                if cursor.rowcount > 0:
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
        if is_postgres():
            if not pool:
                await init_db()

            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE contacts 
                    SET click_count = click_count + 1 
                    WHERE service = $1
                """, service)
                return True
        else:
            # SQLite
            if not sqlite_conn:
                await init_db()

            await sqlite_conn.execute("""
                UPDATE contacts 
                SET click_count = click_count + 1 
                WHERE service = ?
            """, (service,))
            await sqlite_conn.commit()
            return True

    except Exception as e:
        print(f"❌ Click count oshirish xatosi: {e}")
        return False


async def get_top_contacts(limit: int = 8):
    """Eng ko'p bosilgan kontaktlarni olish"""
    try:
        if is_postgres():
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
        else:
            # SQLite
            if not sqlite_conn:
                await init_db()

            query = f"""
                SELECT service, phone, click_count
                FROM contacts 
                WHERE click_count > 0
                ORDER BY click_count DESC
                LIMIT {limit}
            """

            async with sqlite_conn.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [(row[0], row[1], row[2]) for row in rows]

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


async def close_db():
    """Database ulanishini yopish"""
    try:
        if is_postgres() and pool:
            await pool.close()
            print("✅ PostgreSQL pool yopildi.")
        elif sqlite_conn:
            await sqlite_conn.close()
            print("✅ SQLite connection yopildi.")
    except Exception as e:
        print(f"❌ Database yopish xatosi: {e}")