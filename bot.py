import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ChatMemberStatus, ParseMode
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BotCommand,
    BotCommandScopeDefault,
    ChatMemberUpdated
)
from aiogram.filters import Command, CommandObject, ChatMemberUpdatedFilter
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ADMIN_IDS, ALLOWED_GROUP_IDS, DEV_NAME, DEV_USERNAME, BOT_USERNAME, print_config
import db

# =================== BOT YARATISH ===================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# =================== YORDAMCHI FUNKSIYALAR ===================
def is_allowed_chat(chat_id: int) -> bool:
    """Guruh tekshiruvi - bir nechta guruhlar uchun"""
    return str(chat_id) in ALLOWED_GROUP_IDS


def is_admin(user_id: int) -> bool:
    """Admin tekshiruvi - bir nechta adminlar uchun"""
    return user_id in ADMIN_IDS


def create_main_menu(is_admin_user: bool = False):
    """Asosiy menyu"""
    buttons = [
        [InlineKeyboardButton(text="📞 Tezkor aloqa", callback_data="menu:contacts")],
        [InlineKeyboardButton(text="🔥 Mashhur 8ta raqam", callback_data="menu:top")],
        [InlineKeyboardButton(text="🆔 ID ma'lumotlari", callback_data="menu:id")],
        [InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="menu:about")],
    ]

    if is_admin_user:
        buttons.insert(2, [InlineKeyboardButton(text="👤 Admin panel", callback_data="menu:admin")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_admin_menu():
    """Admin menyusi"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kontakt qo'shish", callback_data="admin:add")],
            [InlineKeyboardButton(text="🗑️ Kontakt o'chirish", callback_data="admin:delete")],
            [InlineKeyboardButton(text="📋 Kontaktlar ro'yxati", callback_data="menu:contacts")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
        ]
    )


def format_phone_for_display(phone: str) -> str:
    """Telefon raqamini formatlamasdan ko'rsatish"""
    if not phone:
        return ""
    return phone.strip()


def is_valid_phone(phone: str) -> bool:
    """Telefon raqami to'g'ri formatdami tekshirish"""
    if not phone:
        return False

    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

    if not cleaned:
        return False

    # Qisqa raqamlar (102, 103, 911 kabi)
    if cleaned.isdigit() and 2 <= len(cleaned) <= 5:
        return True

    # Uzun raqamlar
    if cleaned.startswith("+998") and len(cleaned) == 13:
        return True
    elif cleaned.startswith("998") and len(cleaned) == 12:
        return True
    elif cleaned.isdigit() and len(cleaned) == 9:  # 901234567
        return True
    elif cleaned.isdigit() and len(cleaned) == 12:  # 998901234567
        return True

    return False


def get_phone_type(phone: str) -> str:
    """Telefon raqami turini aniqlash"""
    if not phone:
        return "invalid"

    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

    if not cleaned:
        return "invalid"

    # Qisqa raqamlar (102,103,911 kabi)
    if cleaned.isdigit() and 2 <= len(cleaned) <= 5:
        return "short"

    # Uzun raqamlar
    if cleaned.startswith("+998") and len(cleaned) == 13:
        return "uzbek_long"
    elif cleaned.startswith("998") and len(cleaned) == 12:
        return "uzbek_long"
    elif cleaned.isdigit() and len(cleaned) == 9:  # 901234567
        return "uzbek_long"
    elif cleaned.isdigit() and len(cleaned) == 12:  # 998901234567
        return "uzbek_long"

    return "invalid"


async def setup_bot_commands():
    """Bot command larini sozlash"""
    commands = [
        BotCommand(command="start", description="🤖 Botni ishga tushirish"),
        BotCommand(command="aloqa", description="📞 Tezkor aloqa raqamlari"),
        BotCommand(command="top", description="🔥 Mashhur 8ta raqam"),
        BotCommand(command="id", description="🆔 ID ma'lumotlari"),
        BotCommand(command="yordam", description="❓ Bot haqida ma'lumot"),
    ]

    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        print("✅ Bot command lar sozlandi")
    except Exception as e:
        print(f"⚠️  Command sozlash xatosi: {e}")


# =================== MENU TARIXI BOSHQARISH ===================
async def add_menu_to_history(call: CallbackQuery, menu_name: str = None):
    """Menyuni tarixga qo'shish"""
    if menu_name is None:
        if call.data.startswith("menu:"):
            menu_name = call.data.split(":", 1)[1]
        elif call.data.startswith("admin:"):
            menu_name = f"admin:{call.data.split(':', 1)[1]}"
        else:
            menu_name = "main"

    db.add_to_menu_history(call.from_user.id, menu_name)


async def go_back(call: CallbackQuery):
    """Orqaga qaytish"""
    previous_menu = db.get_previous_menu(call.from_user.id)

    if previous_menu is None:
        # Agar tarix bo'lmasa, asosiy menyuga qaytamiz
        await handle_menu(call, "main")
        return True

    # Oldingi menyuga qaytamiz
    if previous_menu.startswith("menu:"):
        menu_option = previous_menu.split(":", 1)[1]
        await handle_menu(call, menu_option)
    elif previous_menu == "main":
        await handle_menu(call, "main")
    elif previous_menu.startswith("admin:"):
        admin_action = previous_menu.split(":", 1)[1]
        await handle_admin_actions(call, admin_action)
    else:
        await handle_menu(call, "main")

    return True


# =================== BOT QO'SHILISHINI CHEKLASH ===================
@dp.my_chat_member()
async def restrict_bot_join(event: ChatMemberUpdated):
    """Bot faqat ruxsat berilgan guruhga qo'shilishini ta'minlash"""
    chat = event.chat
    new_status = event.new_chat_member.status

    # Bot chatdan o'chirilgan bo'lsa
    if new_status == ChatMemberStatus.LEFT:
        print(f"🚪 Bot chatdan chiqdi: {chat.id}")
        return

    # Bot qo'shilgan holatlar
    if new_status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        return

    print(f"🤖 Bot qo'shildi: {chat.id} | type={chat.type}")

    # Kanalga qo'shilsa
    if chat.type == ChatType.CHANNEL:
        await bot.leave_chat(chat.id)
        print(f"❌ Kanalga qo'shildi, chiqildi.")
        return

    # Guruh / superguruh bo'lsa
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        if not is_allowed_chat(chat.id):
            await bot.leave_chat(chat.id)
            print(f"❌ Ruxsatsiz guruhdan chiqildi: {chat.id}")
            return

        print(f"✅ Ruxsat berilgan guruhga qo'shildi: {chat.id}")
        # Guruhga xabar yuborish
        welcome_text = (
            "✅ <b>Mahalla Aloqa Boti ushbu guruhga biriktirildi.</b>\n\n"
            "📞 <b>Tezkor aloqa raqamlari:</b> /aloqa\n"
            "🔥 <b>Mashhur raqamlar:</b> /top\n"
            "🤖 <b>Bot haqida:</b> /yordam\n\n"
        )

        if is_admin(event.from_user.id):
            welcome_text += (
                "<i>Admin: Yangi kontakt qo'shish uchun /qoshish buyrug'idan foydalaning</i>"
            )

        await bot.send_message(chat.id, welcome_text)


# =================== START VA YORDAM ===================
@dp.message(Command("start", "help", "yordam"))
async def cmd_start(message: Message):
    """Botni ishga tushirish"""
    if not is_allowed_chat(message.chat.id):
        return

    is_admin_user = is_admin(message.from_user.id)

    welcome_text = (
        "🤖 <b>Mahalla Tezkor Aloqa Boti</b>\n\n"
        "📍 <i>Mahallangiz uchun zarur bo'lgan barcha aloqa raqamlari bir joyda!</i>\n\n"
        "🔸 <b>Mavjud buyruqlar:</b>\n"
        "• /aloqa - Tezkor aloqa raqamlari\n"
        "• /top - Mashhur 8ta kontakt\n"
    )

    welcome_text += (
        "• /id - Chat va foydalanuvchi ID si\n"
        "• /yordam - Bot haqida ma'lumot\n\n"
        "👇 <b>Pastdagi menyu tugmalaridan foydalaning:</b>"
    )

    await message.answer(welcome_text, reply_markup=create_main_menu(is_admin_user))

    # Menyu tarixiga qo'shamiz
    db.add_to_menu_history(message.from_user.id, "main")


# =================== KONTAKTNI KO'RSATISH ===================
@dp.callback_query(F.data.startswith("contact:"))
async def show_contact_details(call: CallbackQuery):
    """Kontakt tafsilotlarini ko'rsatish"""
    try:
        if not is_allowed_chat(call.message.chat.id):
            await call.answer("❌ Ruxsat yo'q", show_alert=True)
            return

        # Callback datani ajratish
        data_parts = call.data.split(":", 2)

        if len(data_parts) < 3:
            await call.answer("❌ Format xatosi", show_alert=True)
            return

        service = data_parts[1]
        phone = data_parts[2]

        # Click count ni oshirish
        await db.increment_click_count(service)

        phone_type = get_phone_type(phone)
        formatted_phone = format_phone_for_display(phone)

        # Tugmalarni yaratish
        buttons = []

        if phone_type == "short":
            buttons.append([
                InlineKeyboardButton(
                    text="📞 Raqamni ko'rish",
                    callback_data=f"showphone:{phone}"
                )
            ])
        elif phone_type == "uzbek_long":
            whatsapp_num = ''.join(c for c in phone if c.isdigit())
            if whatsapp_num.startswith("998"):
                whatsapp_num = whatsapp_num[3:]
            elif whatsapp_num.startswith("+998"):
                whatsapp_num = whatsapp_num[4:]

            buttons.append([
                InlineKeyboardButton(
                    text="📱 Raqamni ko'rish",
                    callback_data=f"showphone:{phone}"
                ),
                InlineKeyboardButton(
                    text="💬 WhatsApp",
                    url=f"https://wa.me/{whatsapp_num}"
                )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    text="📋 Raqamni ko'rish",
                    callback_data=f"showphone:{phone}"
                )
            ])

        # ORQAGA TUGMALARI
        buttons.append([
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back"),
            InlineKeyboardButton(text="📞 Boshqa kontaktlar", callback_data="menu:contacts")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Javob matni
        response = (
            f"👤 <b>{service}</b>\n\n"
            f"📞 <b>Telefon raqami:</b>\n"
            f"<a href='tel:+998901234567'>{formatted_phone}</a>\n\n"
        )

        if phone_type == "short":
            response += "<i>Bu qisqa raqam. Raqamni ko'rish uchun tugmani bosing.</i>"
        elif phone_type == "uzbek_long":
            response += "<i>Raqamni nusxalash uchun tugmani bosing.</i>"
        else:
            response += "<i>Raqam formatini tekshirib, qayta kiriting.</i>"

        await call.message.edit_text(response, reply_markup=keyboard)
        await call.answer()

        # Menyu tarixiga qo'shamiz
        await add_menu_to_history(call, f"contact:{service}")

    except Exception as e:
        print(f"❌ Kontakt ko'rsatish xatosi: {e}")
        await call.answer("❌ Xatolik yuz berdi", show_alert=True)


# =================== ALOQA RAQAMLARI ===================
@dp.message(Command("aloqa", "contact", "kontakt"))
async def cmd_contacts(message: Message):
    """Tezkor aloqa raqamlari"""
    if not is_allowed_chat(message.chat.id):
        return

    contacts = await db.get_contacts()

    if not contacts:
        await message.answer(
            "📭 <b>Hozircha aloqa raqamlari yo'q.</b>\n\n"
            "Admin yangi raqam qo'shishi mumkin:\n"
            "<code>Xizmat nomi | Raqam</code>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )
        return

    buttons = []
    for service, phone in contacts:
        # Faqat service nomini ko'rsatamiz
        buttons.append([
            InlineKeyboardButton(
                text=f"📱 {service}",
                callback_data=f"contact:{service}:{phone}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="🔥 Mashhur 8ta", callback_data="menu:top"),
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        "🚨 <b>Tezkor aloqa xizmatlari:</b>\n\n"
        f"<i>Jami {len(contacts)} ta kontakt mavjud</i>",
        reply_markup=keyboard
    )

    # Menyu tarixiga qo'shamiz
    db.add_to_menu_history(message.from_user.id, "contacts")


# =================== TOP 8 KONTAKTLAR ===================
@dp.message(Command("top"))
async def cmd_top_contacts(message: Message):
    """Eng ko'p bosilgan 8ta kontakt"""
    if not is_allowed_chat(message.chat.id):
        return

    top_contacts = await db.get_top_contacts(8)

    if not top_contacts:
        await message.answer(
            "📊 <b>Hozircha hech qanday kontakt bosilmagan.</b>\n\n"
            "Kontaktlarni bosing, statistika to'planadi.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📞 Kontaktlar ro'yxati", callback_data="menu:contacts")],
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )
        return

    buttons = []
    for i, (service, phone, click_count) in enumerate(top_contacts, 1):
        emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"][i - 1]
        display_text = f"{emoji} {service} ({click_count})"

        buttons.append([
            InlineKeyboardButton(
                text=display_text,
                callback_data=f"contact:{service}:{phone}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="📞 Barcha kontaktlar", callback_data="menu:contacts"),
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        "🔥 <b>Eng ko'p qidirilgan 8ta kontakt:</b>\n\n"
        "<i>Kontaktlar bosilish soni bo'yicha tartiblangan</i>",
        reply_markup=keyboard
    )

    # Menyu tarixiga qo'shamiz
    db.add_to_menu_history(message.from_user.id, "top")


# =================== RAQAMNI KO'RSATISH ===================
@dp.callback_query(F.data.startswith("showphone:"))
async def show_phone_handler(call: CallbackQuery):
    """Raqamni to'liq ko'rsatish"""
    try:
        phone = call.data.split(":", 1)[1]
        formatted_phone = format_phone_for_display(phone)
        phone_type = get_phone_type(phone)

        response = f"📱 <b>Telefon raqami:</b>\n\n<code>{formatted_phone}</code>\n\n"

        if phone_type == "short":
            response += "🔹 <b>Qisqa raqam:</b> To'g'ridan-to'g'ri telefoningizdan terishingiz mumkin\n"
        elif phone_type == "uzbek_long":
            response += "📝 <b>Qo'llanma:</b>\n"
            response += "1. Raqamni bosing (nusxalanadi)\n"
            response += "2. Telefon dasturingizga o'ting\n"
            response += "3. Terish maydoniga yopishtiring\n"
        else:
            response += "⚠️ <b>Eslatma:</b> Raqam formatini tekshirib, qayta kiriting\n"

        # Tugmalar
        buttons = []

        if phone_type == "uzbek_long":
            whatsapp_num = ''.join(c for c in phone if c.isdigit())
            if whatsapp_num.startswith("998"):
                whatsapp_num = whatsapp_num[3:]
            elif whatsapp_num.startswith("+998"):
                whatsapp_num = whatsapp_num[4:]

            buttons.append([
                InlineKeyboardButton(
                    text="💬 WhatsApp orqali yozish",
                    url=f"https://wa.me/{whatsapp_num}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await call.message.answer(response, reply_markup=keyboard)
        await call.answer("✅ Raqam yuborildi! Nusxalash uchun raqamni bosing.")

        # Menyu tarixiga qo'shamiz
        await add_menu_to_history(call, f"showphone:{phone}")

    except Exception as e:
        print(f"❌ Raqam ko'rsatish xatosi: {e}")
        await call.answer("❌ Xatolik", show_alert=True)


# =================== ADMIN FUNKSIYALARI ===================
@dp.message(Command("qoshish", "add"))
async def cmd_add_contact(message: Message, command: CommandObject):
    """Yangi kontakt qo'shish"""
    if not is_allowed_chat(message.chat.id) or not is_admin(message.from_user.id):
        return

    if not command.args:
        await message.answer(
            "📝 <b>Kontakt qo'shish formati:</b>\n"
            "<code>Ism | Raqam</code>\n\n"
            "📌 <b>TO'G'RI MISOLLAR:</b>\n"
            "<code>Tez yordam | 103</code>\n"
            "<code>Elektrik usta | +998901234567</code>\n"
            "<code>Elektrik usta | 998901234567</code>\n"
            "<code>Elektrik usta | 901234567</code>\n",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )
        return

    try:
        if "|" not in command.args:
            await message.answer(
                "❌ Noto'g'ri format! '|' belgisidan foydalaning.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        parts = command.args.split("|", 1)
        service = parts[0].strip()
        phone = parts[1].strip()

        if not service:
            await message.answer(
                "❌ Xizmat nomi bo'sh bo'lmasligi kerak!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        if not phone:
            await message.answer(
                "❌ Telefon raqami bo'sh bo'lmasligi kerak!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        if not is_valid_phone(phone):
            await message.answer(
                "❌ <b>Telefon raqami noto'g'ri formatda!</b>\n\n"
                "✅ <b>Qabul qilinadigan formatlar:</b>\n"
                "• Qisqa raqamlar: 103, 911, 112 (2-5 raqam)\n"
                "• O'zbekiston raqamlari:\n"
                "  - +998901234567\n"
                "  - 998901234567\n"
                "  - 901234567",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        success = await db.update_contact(service, phone)

        if success:
            phone_type = get_phone_type(phone)

            await message.answer(
                f"✅ <b>Kontakt qo'shildi:</b>\n\n"
                f"📋 <b>Xizmat:</b> {service}\n"
                f"📞 <b>Raqam:</b> <code>{phone}</code>\n"
                f"🔹 <b>Turi:</b> {'Qisqa raqam' if phone_type == 'short' else 'Oʻzbekiston raqami'}\n\n"
                f"<i>Endi /aloqa orqali ko'rishingiz mumkin.</i>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📊 Kontaktlar ro'yxati", callback_data="menu:contacts")],
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
        else:
            await message.answer(
                "❌ <b>Kontakt saqlashda xatolik!</b>\n\n"
                "<i>Iltimos, qayta urinib ko'ring.</i>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )

    except Exception as e:
        print(f"❌ Saqlash xatosi: {e}")
        await message.answer(
            f"❌ <b>Xatolik:</b> {str(e)}\n\n"
            "<i>Iltimos, formatni tekshiring va qayta urinib ko'ring.</i>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )


# =================== MATN ORQALI KONTAKT QO'SHISH ===================
@dp.message(F.text.contains(" | "), F.from_user.id.in_(ADMIN_IDS))
async def handle_contact_text(message: Message):
    """Admin tomonidan matn orqali kontakt qo'shish"""
    if not is_allowed_chat(message.chat.id):
        return

    try:
        parts = message.text.split(" | ", 1)
        service = parts[0].strip()
        phone = parts[1].strip()

        if not service or not phone:
            await message.answer(
                "❌ Xizmat nomi yoki raqam bo'sh bo'lishi mumkin emas!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        if not is_valid_phone(phone):
            await message.answer(
                "❌ <b>Telefon raqami noto'g'ri formatda!</b>\n\n"
                "✅ <b>Qabul qilinadigan formatlar:</b>\n"
                "• Qisqa raqamlar: 103, 911, 112 (2-5 raqam)\n"
                "• O'zbekiston raqamlari:\n"
                "  - +998901234567\n"
                "  - 998901234567\n"
                "  - 901234567",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        success = await db.update_contact(service, phone)

        if success:
            phone_type = get_phone_type(phone)
            await message.answer(
                f"✅ <b>Kontakt qo'shildi:</b>\n\n"
                f"📋 <b>Xizmat:</b> {service}\n"
                f"📞 <b>Raqam:</b> <code>{phone}</code>\n"
                f"🔹 <b>Turi:</b> {'Qisqa raqam' if phone_type == 'short' else 'Oʻzbekiston raqami'}\n\n"
                f"<i>Endi /aloqa orqali ko'rishingiz mumkin.</i>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📊 Kontaktlar ro'yxati", callback_data="menu:contacts")],
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
        else:
            await message.answer(
                "❌ <b>Kontakt saqlashda xatolik!</b>\n\n"
                "<i>Iltimos, qayta urinib ko'ring.</i>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )

    except Exception as e:
        print(f"❌ Saqlash xatosi: {e}")
        await message.answer(
            f"❌ <b>Xatolik:</b> {str(e)}\n\n"
            "<i>Iltimos, formatni tekshiring va qayta urinib ko'ring.</i>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )


@dp.message(Command("ochirish", "delete", "remove"))
async def cmd_delete_contact(message: Message, command: CommandObject):
    """Kontaktni o'chirish"""
    if not is_allowed_chat(message.chat.id) or not is_admin(message.from_user.id):
        return

    if not command.args:
        contacts = await db.get_contacts_with_clicks()
        if not contacts:
            await message.answer(
                "📭 O'chirish uchun kontaktlar yo'q.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        buttons = []
        for service, phone, click_count in contacts:
            display_phone = phone[:15] + "..." if len(phone) > 15 else phone
            buttons.append([
                InlineKeyboardButton(
                    text=f"❌ {service} ({display_phone})",
                    callback_data=f"delete:{service}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer(
            "🗑️ <b>O'chirish uchun kontaktni tanlang:</b>",
            reply_markup=keyboard
        )
        return

    try:
        service = command.args.strip()
        success = await db.delete_contact(service)

        if success:
            await message.answer(
                f"✅ Kontakt o'chirildi: <b>{service}</b>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📊 Kontaktlar ro'yxati", callback_data="menu:contacts")],
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
        else:
            await message.answer(
                f"❌ Kontakt topilmadi yoki o'chirishda xatolik!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )


# =================== MENU HANDLERLARI ===================
@dp.callback_query(F.data.startswith("menu:"))
async def handle_menu_callback(call: CallbackQuery):
    """Menyu tugmalarini boshqarish"""
    if not is_allowed_chat(call.message.chat.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    menu_option = call.data.split(":", 1)[1]
    await handle_menu(call, menu_option)


async def handle_menu(call: CallbackQuery, menu_option: str):
    """Menyuni boshqarish"""
    user_id = call.from_user.id
    is_admin_user = is_admin(user_id)

    # Menyu tarixiga qo'shamiz
    await add_menu_to_history(call, f"menu:{menu_option}")

    if menu_option == "main":
        await call.message.edit_text(
            "🤖 <b>Mahalla Tezkor Aloqa Boti</b>\n\n"
            "📍 <i>Mahallangiz uchun zarur bo'lgan barcha aloqa raqamlari bir joyda!</i>\n\n"
            "👇 Pastdagi tugmalardan foydalaning:",
            reply_markup=create_main_menu(is_admin_user)
        )

    elif menu_option == "contacts":
        contacts = await db.get_contacts()

        if not contacts:
            await call.message.edit_text(
                "📭 <b>Hozircha aloqa raqamlari yo'q.</b>\n\n"
                "Admin yangi raqam qo'shishi mumkin:\n"
                "<code>Xizmat nomi | Raqam</code>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            await call.answer()
            return

        buttons = []
        for service, phone in contacts:
            buttons.append([
                InlineKeyboardButton(
                    text=f"📱 {service}",
                    callback_data=f"contact:{service}:{phone}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="🔥 Mashhur 8ta", callback_data="menu:top"),
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await call.message.edit_text(
            "🚨 <b>Tezkor aloqa xizmatlari:</b>\n\n"
            f"<i>Jami {len(contacts)} ta kontakt mavjud</i>",
            reply_markup=keyboard
        )

    elif menu_option == "top":
        top_contacts = await db.get_top_contacts(8)

        if not top_contacts:
            await call.message.edit_text(
                "📊 <b>Hozircha hech qanday kontakt bosilmagan.</b>\n\n"
                "Kontaktlarni bosing, statistika to'planadi.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📞 Kontaktlar ro'yxati", callback_data="menu:contacts")],
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            await call.answer()
            return

        buttons = []
        for i, (service, phone, click_count) in enumerate(top_contacts, 1):
            emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"][i - 1]
            display_text = f"{emoji} {service} ({click_count})"

            buttons.append([
                InlineKeyboardButton(
                    text=display_text,
                    callback_data=f"contact:{service}:{phone}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="📞 Barcha kontaktlar", callback_data="menu:contacts"),
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await call.message.edit_text(
            "🔥 <b>Eng ko'p qidirilgan 8ta kontakt:</b>\n\n"
            "<i>Kontaktlar bosilish soni bo'yicha tartiblangan</i>",
            reply_markup=keyboard
        )

    elif menu_option == "about":
        dev_clean = DEV_USERNAME.lstrip('@')
        bot_clean = BOT_USERNAME.lstrip('@')

        about_text = (
            f"ℹ️ <b>Bot haqida ma'lumot</b>\n\n"
            f"📌 <b>Maqsad:</b> Mahalla a'zolari uchun barcha zarur "
            f"aloqa raqamlarini bir joyda to'plash va ularga tez yetishish.\n\n"
            f"⚙️ <b>Imkoniyatlar:</b>\n"
            f"• Tezkor aloqa raqamlari\n"
            f"• WhatsApp orqali yozish\n"
            f"• Raqamlarni nusxalash\n"
            f"• Mashhur 8ta raqam\n"
            f"• Admin panel (faqat admin uchun)\n\n"
            f"👨‍💻 Dasturchi: <a href='https://t.me/{DEV_USERNAME}'>{DEV_NAME}</a>\n\n"
            f"🤖 <b>Bot:</b> <a href='https://t.me/{bot_clean}'>@{bot_clean}</a>\n\n"
            f"💡 <i>Taklif va shikoyatlar uchun dasturchi bilan bog'laning.</i>"



        )

        buttons = []
        if dev_clean:
            buttons.append([InlineKeyboardButton(text="👨‍💻 Dasturchi", url=f"https://t.me/{dev_clean}")])

        buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await call.message.edit_text(about_text, reply_markup=keyboard)

    elif menu_option == "id":
        user_username = call.from_user.username
        username_display = f"@{user_username}" if user_username else "Yo'q"

        is_user_admin = is_admin(call.from_user.id)

        response = (
            f"🆔 <b>ID MA'LUMOTLARI:</b>\n\n"
            f"• <b>Chat ID:</b> <code>{call.message.chat.id}</code>\n"
            f"• <b>Chat turi:</b> {call.message.chat.type}\n"
            f"• <b>Sizning ID:</b> <code>{call.from_user.id}</code>\n"
            f"• <b>Username:</b> {username_display}\n"
            f"• <b>Admin statusi:</b> {'✅ HA' if is_user_admin else '❌ YO‘Q'}\n\n"
            f"<i>Bot faqat ruxsat berilgan guruhda ishlaydi.</i>"
        )

        await call.message.edit_text(
            response,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )

    elif menu_option == "admin":
        if not is_admin_user:
            await call.answer("❌ Siz admin emassiz", show_alert=True)
            return

        await call.message.edit_text(
            "👤 <b>Admin panel</b>\n\n"
            "📋 <b>Admin funksiyalari:</b>\n\n"
            "• Kontakt qo'shish / o'chirish\n\n"
            "👇 <b>Tugmalardan foydalaning:</b>",
            reply_markup=create_admin_menu()
        )

    await call.answer()


# =================== ADMIN ACTION HANDLERLAR ===================
@dp.callback_query(F.data.startswith("admin:"))
async def handle_admin_callback(call: CallbackQuery):
    """Admin harakatlari"""
    if not is_allowed_chat(call.message.chat.id) or not is_admin(call.from_user.id):
        await call.answer("❌ Admin emassiz", show_alert=True)
        return

    action = call.data.split(":", 1)[1]
    await handle_admin_actions(call, action)


async def handle_admin_actions(call: CallbackQuery, action: str):
    """Admin harakatlarini boshqarish"""
    # Menyu tarixiga qo'shamiz
    await add_menu_to_history(call, f"admin:{action}")

    if action == "add":
        await call.message.edit_text(
            "📝 <b>Kontakt qo'shish formati:</b>\n"
            "<code>Ism | Raqam</code>\n\n"
            "📌 <b>TO'G'RI MISOLLAR:</b>\n"
            "<code>Tez yordam | 103</code>\n"
            "<code>Elektrik usta | +998901234567</code>\n"
            "<code>Elektrik usta | 998901234567</code>\n"
            "<code>Elektrik usta | 901234567</code>\n",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )

    elif action == "delete":
        contacts = await db.get_contacts_with_clicks()
        if not contacts:
            await call.message.edit_text(
                "📭 O'chirish uchun kontaktlar yo'q.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            await call.answer()
            return

        buttons = []
        for service, phone, click_count in contacts:
            display_phone = phone[:15] + "..." if len(phone) > 15 else phone
            buttons.append([
                InlineKeyboardButton(
                    text=f"❌ {service} ({display_phone})",
                    callback_data=f"delete:{service}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await call.message.edit_text(
            "🗑️ <b>O'chirish uchun kontaktni tanlang:</b>",
            reply_markup=keyboard
        )

    await call.answer()


# =================== O'CHIRISH CALLBACK ===================
@dp.callback_query(F.data.startswith("delete:"))
async def handle_delete(call: CallbackQuery):
    """Kontaktni o'chirish"""
    if not is_allowed_chat(call.message.chat.id) or not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    service = call.data.split(":", 1)[1]

    try:
        success = await db.delete_contact(service)

        if success:
            await call.message.edit_text(
                f"✅ <b>Kontakt o'chirildi:</b>\n\n"
                f"<i>Boshqa kontaktlarni ko'rish uchun /aloqa buyrug'idan foydalaning.</i>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📊 Kontaktlar ro'yxati", callback_data="menu:contacts")],
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            await call.answer("✅ O'chirildi")
        else:
            await call.answer("❌ O'chirishda xatolik", show_alert=True)

    except Exception as e:
        await call.answer(f"❌ Xatolik: {str(e)}", show_alert=True)


# =================== ORQAGA QAYTISH ===================
@dp.callback_query(F.data == "back")
async def handle_back(call: CallbackQuery):
    """Orqaga qaytish"""
    success = await go_back(call)
    if not success:
        await call.answer("❌ Orqaga qaytish mumkin emas", show_alert=True)


# =================== ID BUYRUQ'I ===================
@dp.message(Command("id"))
async def cmd_id(message: Message):
    """ID ma'lumotlarini ko'rsatish"""
    if not is_allowed_chat(message.chat.id):
        return

    user_username = message.from_user.username
    username_display = f"@{user_username}" if user_username else "Yo'q"

    is_user_admin = is_admin(message.from_user.id)

    response = (
        f"🆔 <b>ID MA'LUMOTLARI:</b>\n\n"
        f"• <b>Chat ID:</b> <code>{message.chat.id}</code>\n"
        f"• <b>Chat turi:</b> {message.chat.type}\n"
        f"• <b>Sizning ID:</b> <code>{message.from_user.id}</code>\n"
        f"• <b>Username:</b> {username_display}\n"
        f"• <b>Admin statusi:</b> {'✅ HA' if is_user_admin else '❌ YOQ'}\n\n"
        f"<i>Bot faqat ruxsat berilgan guruhda ishlaydi.</i>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
        ]
    )

    await message.answer(response, reply_markup=keyboard)


# =================== DEBUG HANDLER ===================
@dp.message()
async def debug_handler(message: Message):
    """Debug handler"""
    if message.text and message.text.startswith('/'):
        print(f"🔴 ISHLANMAGAN BUYRUQ: '{message.text}'")
        print(f"   👤 User: {message.from_user.id}")
        print(f"   💬 Chat: {message.chat.id}")

        if is_allowed_chat(message.chat.id):
            is_admin_user = is_admin(message.from_user.id)
            await message.answer(
                f"❌ <b>'{message.text}' buyrug'i topilmadi!</b>\n\n"
                f"📋 <b>Mavjud buyruqlar:</b>\n"
                f"• /aloqa - Tezkor aloqa raqamlari\n"
                f"• /top - Mashhur 8ta kontakt\n"
                f"• /id - ID ma'lumotlari\n"
                f"• /yordam - Bot haqida ma'lumot\n"
                f"\n<i>Yoki menyu tugmalaridan foydalaning 👇</i>",
                reply_markup=create_main_menu(is_admin_user)
            )


# =================== ASOSIY FUNKSIYA ===================
async def main():
    """Asosiy bot funksiyasi"""
    print("=" * 60)
    print("🤖 MAHALLA ALOQA BOTI ISHGA TUSHMOGDA...")

    # Sozlamalarni chiqarish
    print_config()

    print("=" * 60)

    # Database ga ulanish
    db_ok = await db.init_db()
    if not db_ok:
        print("❌ Database bilan muammo! Bot ishlamaydi.")
        return

    print("✅ Bot tayyor!")
    print("=" * 60)

    # Botni ishga tushirish
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"❌ Bot xatosi: {e}")
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())