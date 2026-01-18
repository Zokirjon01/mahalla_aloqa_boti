import os
from dotenv import load_dotenv

# 1. Avval .env.local ni yuklashga urinib ko'ramiz
if os.path.exists(".env.local"):
    load_dotenv(".env.local")
    print("📁 .env.local faylidan sozlamalar yuklandi")
elif os.path.exists(".env"):
    load_dotenv(".env")
    print("📁 .env faylidan sozlamalar yuklandi")
else:
    print("⚠️  Hech qanday .env fayli topilmadi")

# Asosiy sozlamalar - faqat .env faylidan o'qiladi
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "").strip()
ALLOWED_GROUP_IDS_STR = os.getenv("ALLOWED_GROUP_IDS", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL")  # Faqat .env dan
DEV_NAME = os.getenv("DEV_NAME", "developer_name")
DEV_USERNAME = os.getenv("DEV_USERNAME", "developer_username")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MahallaYordamBot")

# Admin ID larini listga o'tkazish
ADMIN_IDS = []
if ADMIN_IDS_STR:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()]

# Gruh ID larini listga o'tkazish
ALLOWED_GROUP_IDS = []
if ALLOWED_GROUP_IDS_STR:
    ALLOWED_GROUP_IDS = [group_id.strip() for group_id in ALLOWED_GROUP_IDS_STR.split(",") if group_id.strip()]


# Sozlamalarni chiqarish funksiyasi
def print_config():
    """Sozlamalarni ekranga chiqarish"""
    lines = []

    lines.append("⚙️ Sozlamalar yuklandi:")
    lines.append(f"   🤖 Bot: @{BOT_USERNAME}")
    lines.append(f"   👥 Ruxsat berilgan guruhlar: {ALLOWED_GROUP_IDS}")
    lines.append(f"   👤 Adminlar: {ADMIN_IDS}")
    lines.append(f"   🗄️  Database URL mavjud: {'✅ HA' if DATABASE_URL else '❌ YOQ'}")

    # Barcha xabarlarni bir vaqtda chiqaramiz
    for line in lines:
        print(line)