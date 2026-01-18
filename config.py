import os
from dotenv import load_dotenv

# Railway yoki Render da ishlayotganimizni aniqlash
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None
IS_RENDER = os.getenv("RENDER") is not None
IS_PRODUCTION = IS_RAILWAY or IS_RENDER

if not IS_PRODUCTION:
    # Faqat local developmentda .env fayllarini yuklash
    env_loaded = False
    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
        env_loaded = True
        print("📁 .env.local faylidan sozlamalar yuklandi")
    elif os.path.exists(".env"):
        load_dotenv(".env")
        env_loaded = True
        print("📁 .env faylidan sozlamalar yuklandi")

    if not env_loaded:
        print("⚠️  Local: .env fayli topilmadi, environment variables dan foydalanilmoqda")
else:
    # Production (Railway/Render) da .env faylini qidirmaymiz
    print("🚀 Production muhiti (Railway/Render) - environment variables ishlatilmoqda")

# Asosiy sozlamalar
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Bir nechta adminlar uchun
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = []
if ADMIN_IDS_STR:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()]
else:
    if not IS_PRODUCTION:  # Faqat localda xabar chiqaramiz
        print("⚠️  ADMIN_IDS .env faylida to'ldirilmagan!")

# Bir nechta guruhlar uchun
ALLOWED_GROUP_IDS_STR = os.getenv("ALLOWED_GROUP_IDS", "").strip()
ALLOWED_GROUP_IDS = []
if ALLOWED_GROUP_IDS_STR:
    ALLOWED_GROUP_IDS = [group_id.strip() for group_id in ALLOWED_GROUP_IDS_STR.split(",") if group_id.strip()]
else:
    if not IS_PRODUCTION:  # Faqat localda xabar chiqaramiz
        print("⚠️  ALLOWED_GROUP_IDS .env faylida to'ldirilmagan!")

DATABASE_URL = os.getenv("DATABASE_URL")

# Qo'shimcha
DEV_NAME = os.getenv("DEV_NAME", "developer_name")
DEV_USERNAME = os.getenv("DEV_USERNAME", "developer_username")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MahallaYordamBot")


# Sozlamalarni chiqarish funksiyasi
def print_config():
    """Sozlamalarni ekranga chiqarish"""
    print(f"⚙️ Sozlamalar yuklandi:")
    print(f"   🤖 Bot: @{BOT_USERNAME}")
    print(f"   👥 Ruxsat berilgan guruhlar: {ALLOWED_GROUP_IDS}")
    print(f"   👤 Adminlar: {ADMIN_IDS}")
    print(f"   🗄️  Database URL mavjud: {'✅ HA' if DATABASE_URL else '❌ YOQ'}")
    if IS_PRODUCTION:
        print(f"   🌍 Muhit: {'Railway' if IS_RAILWAY else 'Render' if IS_RENDER else 'Local'}")