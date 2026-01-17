import os
from dotenv import load_dotenv

load_dotenv()

# Asosiy sozlamalar
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Bir nechta adminlar uchun
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = []
if ADMIN_IDS_STR:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()]
else:
    print("⚠️  ADMIN_IDS .env faylida to'ldirilmagan!")

# Bir nechta guruhlar uchun
ALLOWED_GROUP_IDS_STR = os.getenv("ALLOWED_GROUP_IDS", "").strip()
ALLOWED_GROUP_IDS = []
if ALLOWED_GROUP_IDS_STR:
    ALLOWED_GROUP_IDS = [group_id.strip() for group_id in ALLOWED_GROUP_IDS_STR.split(",") if group_id.strip()]
else:
    print("⚠️  ALLOWED_GROUP_IDS .env faylida to'ldirilmagan!")

DATABASE_URL = os.getenv("DATABASE_URL")

# Qo'shimcha
DEV_NAME = os.getenv("DEV_NAME", "developer_name")
DEV_USERNAME = os.getenv("DEV_USERNAME", "developer_username")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MahallaYordamBot")

print(f"⚙️ Sozlamalar yuklandi:")
print(f"   🤖 Bot: @{BOT_USERNAME}")
print(f"   👥 Ruxsat berilgan guruhlar: {ALLOWED_GROUP_IDS}")
print(f"   👤 Adminlar: {ADMIN_IDS}")