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
    return str(chat_id) in ALLOWED_GROUP_IDS or chat_id > 0


def is_allowed_group(chat_id: int) -> bool:
    """Faqat guruhlar uchun tekshirish"""
    return str(chat_id) in ALLOWED_GROUP_IDS


def is_admin(user_id: int) -> bool:
    """Admin tekshiruvi"""
    return user_id in ADMIN_IDS


def create_main_menu(is_admin_user: bool = False, is_private: bool = False):
    """Asosiy menyu"""
    buttons = []

    if is_private:
        buttons.append([InlineKeyboardButton(text="🆔 Mening ma'lumotlarim", callback_data="menu:myinfo")])
        buttons.append([InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="menu:about")])
    else:
        buttons.append([InlineKeyboardButton(text="📞 Tezkor aloqa", callback_data="menu:contacts")])
        buttons.append([InlineKeyboardButton(text="🔥 Mashhur 8ta raqam", callback_data="menu:top")])
        buttons.append([InlineKeyboardButton(text="🆔 Mening ma'lumotlarim", callback_data="menu:myinfo")])
        buttons.append([InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="menu:about")])

        if is_admin_user:
            buttons.insert(2, [InlineKeyboardButton(text="👤 Admin panel", callback_data="menu:admin")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_admin_menu():
    """Admin menyusi"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kontakt qo'shish", callback_data="admin:add")],
            [InlineKeyboardButton(text="🗑️ Kontakt o'chirish", callback_data="admin:delete")],
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users")],
            [InlineKeyboardButton(text="📋 Kontaktlar ro'yxati", callback_data="menu:contacts")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
        ]
    )


def format_contact_button(service: str, phone: str) -> str:
    """Kontakt tugmasini formatlash"""
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

    if not cleaned:
        return f"📱 {service}"

    if cleaned.isdigit() and 2 <= len(cleaned) <= 5:
        return f"📱 {service} ({cleaned})"

    if len(cleaned) > 5:
        if cleaned.startswith('+998'):
            last_four = cleaned[-4:]
            if len(cleaned) >= 7:
                operator_code = cleaned[4:7]
                return f"📱 {service} ({operator_code}***{last_four})"
        elif cleaned.startswith('998'):
            if len(cleaned) >= 6:
                operator_code = cleaned[3:6]
                last_four = cleaned[-4:]
                return f"📱 {service} ({operator_code}***{last_four})"
        elif len(cleaned) == 9:
            operator_code = cleaned[:3]
            last_four = cleaned[-4:]
            return f"📱 {service} ({operator_code}***{last_four})"

    if len(cleaned) <= 15:
        return f"📱 {service} ({cleaned})"
    else:
        return f"📱 {service} ({cleaned[:12]}...)"


def is_valid_phone(phone: str) -> bool:
    """Telefon raqami to'g'ri formatdami tekshirish"""
    if not phone:
        return False

    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

    if not cleaned:
        return False

    if cleaned.isdigit() and 2 <= len(cleaned) <= 5:
        return True

    if cleaned.startswith("+998") and len(cleaned) == 13:
        return True
    elif cleaned.startswith("998") and len(cleaned) == 12:
        return True
    elif cleaned.isdigit() and len(cleaned) == 9:
        return True
    elif cleaned.isdigit() and len(cleaned) == 12:
        return True

    return False


def create_whatsapp_url(phone: str) -> str:
    """WhatsApp URL yaratish"""
    cleaned = ''.join(c for c in phone if c.isdigit())

    if cleaned.startswith("998"):
        return f"https://wa.me/{cleaned}"
    elif cleaned.startswith("+998"):
        return f"https://wa.me/{cleaned[1:]}"
    elif len(cleaned) == 9:
        return f"https://wa.me/998{cleaned}"
    else:
        return f"https://wa.me/{cleaned}"


async def setup_bot_commands():
    """Bot command larini sozlash"""
    commands = [
        BotCommand(command="start", description="🤖 Botni ishga tushirish"),
        BotCommand(command="myinfo", description="🆔 Mening ma'lumotlarim"),
        BotCommand(command="aloqa", description="📞 Tezkor aloqa raqamlari"),
        BotCommand(command="top", description="🔥 Mashhur 8ta raqam"),
        BotCommand(command="help", description="❓ Bot haqida ma'lumot"),
    ]

    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        print("✅ Bot command lar sozlandi")
    except Exception as e:
        print(f"⚠️ Command sozlash xatosi: {e}")


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
        await handle_menu(call, "main")
        return True

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


async def save_user_data(user, chat, command: str = None):
    """Foydalanuvchi ma'lumotlarini saqlash"""
    await db.save_user(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        language_code=user.language_code,
        is_bot=user.is_bot,
        is_premium=getattr(user, 'is_premium', False),
        chat_id=chat.id,
        chat_type=chat.type,
        command=command
    )


async def update_user_activity(user_id: int, chat_id: int, command: str = None):
    """Faqat faollikni yangilash"""
    await db.save_user_activity(user_id, chat_id, command)


# =================== BOT QO'SHILISHINI CHEKLASH ===================
@dp.my_chat_member()
async def restrict_bot_join(event: ChatMemberUpdated):
    """Bot faqat ruxsat berilgan guruhga qo'shilishini ta'minlash"""
    chat = event.chat
    new_status = event.new_chat_member.status

    if new_status == ChatMemberStatus.LEFT:
        print(f"🚪 Bot chatdan chiqdi: {chat.id}")
        return

    if new_status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        return

    print(f"🤖 Bot qo'shildi: {chat.id} | type={chat.type}")

    if chat.type == ChatType.CHANNEL:
        await bot.leave_chat(chat.id)
        print(f"❌ Kanalga qo'shildi, chiqildi.")
        return

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        if not is_allowed_group(chat.id):
            await bot.leave_chat(chat.id)
            print(f"❌ Ruxsatsiz guruhdan chiqildi: {chat.id}")
            return

        print(f"✅ Ruxsat berilgan guruhga qo'shildi: {chat.id}")

        welcome_text = (
            "<b>Assalomu alaykum 😊</b>\n\n"
            "<b>Mahalla Tezkor Aloqa Boti</b> ushbu guruhga muvaffaqiyatli biriktirildi.\n\n"
            "📍 <i>Mahallamiz uchun kerakli barcha aloqa raqamlari endi bir joyda!</i>\n\n"
            f"<i>Botni shaxsiy chatda ham ishlatishingiz mumkin: @{BOT_USERNAME.lstrip('@')}</i>\n\n"
            "👇 <b>Pastdagi menyu tugmalaridan foydalaning</b>"
        )

        try:
            msg = await bot.send_message(
                chat.id,
                welcome_text,
                reply_markup=create_main_menu(is_private=False)
            )

            try:
                await bot.pin_chat_message(
                    chat_id=chat.id,
                    message_id=msg.message_id,
                    disable_notification=True
                )
            except:
                pass
        except Exception as e:
            print(f"⚠️ Guruhga xabar yuborishda xatolik: {e}")


# =================== START VA YORDAM ===================
@dp.message(Command("start", "help", "yordam"))
async def cmd_start(message: Message):
    """Botni ishga tushirish"""
    await save_user_data(message.from_user, message.chat, "start")

    is_private = message.chat.type == ChatType.PRIVATE
    is_admin_user = is_admin(message.from_user.id)

    welcome_text = ""
    if is_private:
        welcome_text = (
            "🤖 <b>Mahalla Tezkor Aloqa Botiga xush kelibsiz!</b>\n\n"
            "📍 <i>Bu bot orqali mahalla uchun kerakli barcha aloqa "
            "raqamlariga tez yetishishingiz mumkin.</i>\n\n"
            "🔸 <b>Shaxsiy chatda:</b>\n"
            "• Mening ma'lumotlarimni ko'rish\n"
            "• Bot haqida ma'lumot\n\n"
            "🔹 <b>Guruhda:</b>\n"
            "• Tezkor aloqa raqamlari\n"
            "• Mashhur 8ta raqam\n"
            "• Admin panel (faqat admin)\n\n"
            "👇 <b>Tugmalardan foydalaning:</b>"
        )
    else:
        welcome_text = (
            "🤖 <b>Mahalla Tezkor Aloqa Boti</b>\n\n"
            "📍 <i>Mahalla uchun kerakli barcha aloqa raqamlari endi bir joyda!</i>\n\n"
            "🔸 <b>Mavjud imkoniyatlar:</b>\n"
            "• Tezkor aloqa raqamlari\n"
            "• Mashhur 8ta kontakt\n"
            "• Mening ma'lumotlarim\n"
            "• Bot haqida ma'lumot\n\n"
            "👇 <b>Pastdagi menyu tugmalaridan foydalaning:</b>"
        )

    await message.answer(
        welcome_text,
        reply_markup=create_main_menu(is_admin_user, is_private)
    )
    db.add_to_menu_history(message.from_user.id, "main")


@dp.message(Command("myinfo", "id"))
async def cmd_myinfo(message: Message):
    """Foydalanuvchi ma'lumotlarini ko'rsatish"""
    user = message.from_user
    chat = message.chat

    await update_user_activity(user.id, chat.id, "myinfo")

    user_stats = await db.get_user_stats(user.id)

    if not user_stats:
        if chat.type == ChatType.PRIVATE:
            await message.answer(
                "🤖 <b>Botni ishga tushirish kerak!</b>\n\n"
                "Iltimos, /start buyrug'ini bering yoki quyidagi tugmani bosing:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Start", callback_data="force_start")]
                    ]
                )
            )
        else:
            await message.answer(
                "📨 <i>Sizning ma'lumotlaringiz shaxsiy chatga yuborildi.</i>",
                reply_to_message_id=message.message_id
            )
            try:
                await bot.send_message(
                    chat_id=user.id,
                    text="🤖 <b>Botni ishga tushirish kerak!</b>\n\n"
                         "Iltimos, /start buyrug'ini bering yoki quyidagi tugmani bosing:",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🚀 Start", callback_data="force_start")]
                        ]
                    )
                )
            except Exception:
                await message.answer(
                    f"❌ <i>Sizga xabar yuborib bo'lmadi!"
                    f"Iltimos, avval @{BOT_USERNAME.lstrip('@')} ga start bering.</i>",
                    reply_to_message_id=message.message_id
                )
        return

    stats = await db.get_user_stats(user.id, chat.id)

    if stats:
        started_at = stats.get('started_at')
        if started_at:
            if isinstance(started_at, str):
                started_date = started_at.split(' ')[0]
            else:
                started_date = started_at.strftime('%d.%m.%Y')
        else:
            started_date = "Noma'lum"

        last_activity = stats.get('last_activity')
        if last_activity:
            if isinstance(last_activity, str):
                last_active = last_activity.split(' ')[0]
            else:
                last_active = last_activity.strftime('%d.%m.%Y')
        else:
            last_active = "Bugun"

        response = (
            f"👤 <b>MALUMOTLARINGIZ:</b>\n\n"
            f"🆔 <b>Sizning ID:</b> <code>{user.id}</code>\n"
            f"👤 <b>Ism:</b> {user.first_name or 'Nomalum'}\n"
            f"📝 <b>Familiya:</b> {user.last_name or 'Nomalum'}\n"
            f"📧 <b>Username:</b> @{user.username if user.username else 'Yoq'}\n"
            f"💎 <b>Premium:</b> {'✅ Ha' if getattr(user, 'is_premium', False) else '❌ Yoq'}\n\n"
            f"💬 <b>Chat ID:</b> <code>{chat.id}</code>\n"
            f"📝 <b>Chat turi:</b> {chat.type}\n"
            f"⏰ <b>Birinchi marta:</b> {started_date}\n"
            f"🕐 <b>Oxirgi faollik:</b> {last_active}"
        )
    else:
        response = (
            f"👤 <b>MALUMOTLARINGIZ:</b>\n\n"
            f"🆔 <b>Sizning ID:</b> <code>{user.id}</code>\n"
            f"👤 <b>Ism:</b> {user.first_name or 'Nomalum'}\n"
            f"📝 <b>Familiya:</b> {user.last_name or 'Nomalum'}\n"
            f"📧 <b>Username:</b> @{user.username if user.username else 'Yoq'}\n"
            f"💎 <b>Premium:</b> {'✅ Ha' if getattr(user, 'is_premium', False) else '❌ Yoq'}\n\n"
            f"💬 <b>Chat ID:</b> <code>{chat.id}</code>\n"
            f"📝 <b>Chat turi:</b> {chat.type}"
        )

    if is_admin(user.id):
        response += "\n👤 <b>Admin statusi:</b> ✅ Ha"

    if chat.type == ChatType.PRIVATE:
        await message.answer(
            response,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Yangilash", callback_data="menu:myinfo")],
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )
    else:
        try:
            await bot.send_message(
                chat_id=user.id,
                text=response,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="menu:myinfo")],
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            await message.answer(
                "✅ <i>Ma'lumotlaringiz shaxsiy chatga yuborildi!</i>",
                reply_to_message_id=message.message_id
            )
        except Exception:
            await message.answer(
                f"❌ <i>Men sizga shaxsiy xabar yubora olmayapman. "
                f"Iltimos, avval @{BOT_USERNAME.lstrip('@')} ga start bering.</i>",
                reply_to_message_id=message.message_id
            )


# =================== FORCE START HANDLER ===================
@dp.callback_query(F.data == "force_start")
async def handle_force_start(call: CallbackQuery):
    """Force start handler"""
    await call.answer()
    await save_user_data(call.from_user, call.message.chat, "force_start")

    await call.message.edit_text(
        "✅ <b>Bot muvaffaqiyatli ishga tushdi!</b>\n\n"
        "📍 <i>Endi barcha funksiyalardan foydalanishingiz mumkin.</i>\n\n"
        "👇 <b>Tugmalardan foydalaning:</b>",
        reply_markup=create_main_menu(
            is_admin(call.from_user.id),
            call.message.chat.type == ChatType.PRIVATE
        )
    )
    db.add_to_menu_history(call.from_user.id, "main")


# =================== ALOQA RAQAMLARI ===================
@dp.message(Command("aloqa", "contact", "kontakt"))
async def cmd_contacts(message: Message):
    """Tezkor aloqa raqamlari"""
    # Shaxsiy chatda bloklash
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "❌ <b>Bu buyruq faqat guruhda ishlatilishi mumkin!</b>\n\n"
            "ℹ️ Botni guruhga qo'shing va u yerda ishlating.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🤖 Botni guruhga qo'shish",
                        url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?startgroup=true"
                    )]
                ]
            )
        )
        return

    await update_user_activity(message.from_user.id, message.chat.id, "aloqa")

    if not is_allowed_chat(message.chat.id):
        return

    group_id = message.chat.id
    contacts = await db.get_contacts(group_id)

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
        button_text = format_contact_button(service, phone)
        buttons.append([
            InlineKeyboardButton(
                text=button_text,
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
    db.add_to_menu_history(message.from_user.id, "contacts")


# =================== TOP 8 KONTAKTLAR ===================
@dp.message(Command("top"))
async def cmd_top_contacts(message: Message):
    """Eng ko'p bosilgan 8ta kontakt"""
    # Shaxsiy chatda bloklash
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "❌ <b>Bu buyruq faqat guruhda ishlatilishi mumkin!</b>\n\n"
            "ℹ️ Botni guruhga qo'shing va u yerda ishlating.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🤖 Botni guruhga qo'shish",
                        url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?startgroup=true"
                    )]
                ]
            )
        )
        return

    await update_user_activity(message.from_user.id, message.chat.id, "top")

    if not is_allowed_chat(message.chat.id):
        return

    group_id = message.chat.id
    top_contacts = await db.get_top_contacts(8, group_id)

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
        button_text = format_contact_button(service, phone)
        display_text = f"{emoji} {button_text[2:]} ({click_count})"

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
    db.add_to_menu_history(message.from_user.id, "top")


# =================== ADMIN FUNKSIYALARI ===================
@dp.message(Command("qoshish", "add"))
async def cmd_add_contact(message: Message, command: CommandObject):
    """Yangi kontakt qo'shish"""
    # Shaxsiy chatda bloklash
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "❌ <b>Bu buyruq faqat guruhda ishlatilishi mumkin!</b>\n\n"
            "ℹ️ Kontakt qo'shish uchun botni guruhga qo'shing.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🤖 Botni guruhga qo'shish",
                        url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?startgroup=true"
                    )]
                ]
            )
        )
        return

    await update_user_activity(message.from_user.id, message.chat.id, "add")

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

        if not service or not phone:
            await message.answer(
                "❌ Xizmat nomi yoki raqam bo'sh bo'lmasligi kerak!",
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

        group_id = message.chat.id
        success = await db.update_contact(service, phone, group_id)

        if success:
            await message.answer(
                f"✅ <b>Kontakt qo'shildi:</b>\n\n"
                f"📋 <b>Xizmat:</b> {service}\n"
                f"📞 <b>Raqam:</b> <code>{phone}</code>\n\n"
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
    # Shaxsiy chatda bloklash
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "❌ <b>Kontakt faqat guruhda qo'shilishi mumkin!</b>\n\n"
            "ℹ️ Kontakt qo'shish uchun botni guruhga qo'shing.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🤖 Botni guruhga qo'shish",
                        url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?startgroup=true"
                    )]
                ]
            )
        )
        return

    await update_user_activity(message.from_user.id, message.chat.id, "contact_text")

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

        group_id = message.chat.id
        success = await db.update_contact(service, phone, group_id)

        if success:
            await message.answer(
                f"✅ <b>Kontakt qo'shildi:</b>\n\n"
                f"📋 <b>Xizmat:</b> {service}\n"
                f"📞 <b>Raqam:</b> <code>{phone}</code>\n\n"
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
    # Shaxsiy chatda bloklash
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "❌ <b>Bu buyruq faqat guruhda ishlatilishi mumkin!</b>\n\n"
            "ℹ️ Kontakt o'chirish uchun botni guruhga qo'shing.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🤖 Botni guruhga qo'shish",
                        url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?startgroup=true"
                    )]
                ]
            )
        )
        return

    await update_user_activity(message.from_user.id, message.chat.id, "delete")

    if not is_allowed_chat(message.chat.id) or not is_admin(message.from_user.id):
        return

    group_id = message.chat.id

    if not command.args:
        contacts = await db.get_contacts_with_clicks(group_id)
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
            button_text = format_contact_button(service, phone)
            display_text = f"❌ {button_text[2:]}"
            buttons.append([
                InlineKeyboardButton(
                    text=display_text,
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
        success = await db.delete_contact(service, group_id)

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
    await update_user_activity(call.from_user.id, call.message.chat.id, call.data)

    if not is_allowed_chat(call.message.chat.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    menu_option = call.data.split(":", 1)[1]
    await handle_menu(call, menu_option)


async def handle_menu(call: CallbackQuery, menu_option: str):
    """Menyuni boshqarish"""
    user_id = call.from_user.id
    is_admin_user = is_admin(user_id)
    is_private = call.message.chat.type == ChatType.PRIVATE

    await add_menu_to_history(call, f"menu:{menu_option}")

    if menu_option == "main":
        await call.message.edit_text(
            "🤖 <b>Mahalla Tezkor Aloqa Boti</b>\n\n"
            "📍 <i>Mahalla uchun kerakli barcha aloqa raqamlari endi bir joyda!</i>\n\n"
            "👇 Pastdagi tugmalardan foydalaning:",
            reply_markup=create_main_menu(is_admin_user, is_private)
        )

    elif menu_option == "contacts":
        # Shaxsiy chatda bloklash
        if call.message.chat.type == ChatType.PRIVATE:
            await call.answer(
                f"❌ Bu funksiya faqat guruhda ishlaydi!\n\n"
                f"ℹ️ Botni guruhga qo'shing: @{BOT_USERNAME.lstrip('@')}",
                show_alert=True
            )
            return

        group_id = call.message.chat.id
        contacts = await db.get_contacts(group_id)

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
            button_text = format_contact_button(service, phone)
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
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
        # Shaxsiy chatda bloklash
        if call.message.chat.type == ChatType.PRIVATE:
            await call.answer(
                f"❌ Bu funksiya faqat guruhda ishlaydi!\n\n"
                f"ℹ️ Botni guruhga qo'shing: @{BOT_USERNAME.lstrip('@')}",
                show_alert=True
            )
            return

        group_id = call.message.chat.id
        top_contacts = await db.get_top_contacts(8, group_id)

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
            button_text = format_contact_button(service, phone)
            display_text = f"{emoji} {button_text[2:]} ({click_count})"

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
            f"• Admin panel (faqat admin uchun)\n"
            f"• Shaxsiy ma'lumotlar (faqat o'zingizga ko'rinadi)\n\n"
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

    elif menu_option == "myinfo":
        user = call.from_user
        chat = call.message.chat

        stats = await db.get_user_stats(user.id, chat.id)

        if stats:
            started_at = stats.get('started_at')
            if started_at:
                if isinstance(started_at, str):
                    started_date = started_at.split(' ')[0]
                else:
                    started_date = started_at.strftime('%d.%m.%Y')
            else:
                started_date = "Noma'lum"

            last_activity = stats.get('last_activity')
            if last_activity:
                if isinstance(last_activity, str):
                    last_active = last_activity.split(' ')[0]
                else:
                    last_active = last_activity.strftime('%d.%m.%Y')
            else:
                last_active = "Bugun"

            full_response = (
                f"👤 <b>MA'LUMOTLARINGIZ:</b>\n\n"
                f"🆔 <b>Sizning ID:</b> <code>{user.id}</code>\n"
                f"👤 <b>Ism:</b> {user.first_name or 'Nomalum'}\n"
                f"📝 <b>Familiya:</b> {user.last_name or 'Nomalum'}\n"
                f"📧 <b>Username:</b> @{user.username if user.username else 'Yoq'}\n"
                f"💎 <b>Premium:</b> {'✅ Ha' if getattr(user, 'is_premium', False) else '❌ Yoq'}\n\n"
                f"💬 <b>Chat ID:</b> <code>{chat.id}</code>\n"
                f"📝 <b>Chat turi:</b> {chat.type}\n"
                f"⏰ <b>Birinchi marta:</b> {started_date}\n"
                f"🕐 <b>Oxirgi faollik:</b> {last_active}\n\n"
            )
        else:
            full_response = (
                f"👤 <b>MALUMOTLARINGIZ:</b>\n\n"
                f"🆔 <b>Sizning ID:</b> <code>{user.id}</code>\n"
                f"👤 <b>Ism:</b> {user.first_name or 'Nomalum'}\n"
                f"📝 <b>Familiya:</b> {user.last_name or 'Nomalum'}\n"
                f"📧 <b>Username:</b> @{user.username if user.username else 'Yoq'}\n"
                f"💎 <b>Premium:</b> {'✅ Ha' if getattr(user, 'is_premium', False) else '❌ Yoq'}\n\n"
                f"💬 <b>Chat ID:</b> <code>{chat.id}</code>\n"
                f"📝 <b>Chat turi:</b> {chat.type}"
            )

        if is_admin_user:
            full_response += f"👤 <b>Admin statusi:</b> ✅ Ha"

        if chat.type == ChatType.PRIVATE:
            await call.message.edit_text(
                full_response,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
        else:
            try:
                await bot.send_message(
                    chat_id=user.id,
                    text=full_response,
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                        ]
                    )
                )
                await call.answer(
                    f"✅ Ma'lumotlaringiz shaxsiy chatga yuborildi!\n\n"
                    f"ID: {user.id}\n"
                    f"Ism: {user.first_name[:15] if user.first_name else 'Nomalum'}",
                    show_alert=True
                )
            except Exception:
                await call.answer(
                    f"ID: {user.id}\nIsm: {user.first_name[:15] if user.first_name else 'Nomalum'}",
                    show_alert=True
                )

    elif menu_option == "admin":
        if not is_admin_user:
            await call.answer("❌ Siz admin emassiz", show_alert=True)
            return

        await call.message.edit_text(
            "👤 <b>Admin panel</b>\n\n"
            "📋 <b>Admin funksiyalari:</b>\n\n"
            "• Kontakt qo'shish / o'chirish\n"
            "• Foydalanuvchilar ro'yxati\n"
            "• Kontaktlar ro'yxati\n\n"
            "👇 <b>Tugmalardan foydalaning:</b>",
            reply_markup=create_admin_menu()
        )

    await call.answer()


# =================== ADMIN ACTION HANDLERLAR ===================
@dp.callback_query(F.data.startswith("admin:"))
async def handle_admin_callback(call: CallbackQuery):
    """Admin harakatlari"""
    await update_user_activity(call.from_user.id, call.message.chat.id, call.data)

    if not is_allowed_chat(call.message.chat.id) or not is_admin(call.from_user.id):
        await call.answer("❌ Admin emassiz", show_alert=True)
        return

    action = call.data.split(":", 1)[1]
    await handle_admin_actions(call, action)


async def handle_admin_actions(call: CallbackQuery, action: str):
    """Admin harakatlarini boshqarish"""
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
        group_id = call.message.chat.id
        contacts = await db.get_contacts_with_clicks(group_id)
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
            button_text = format_contact_button(service, phone)
            display_text = f"❌ {button_text[2:]}"

            buttons.append([
                InlineKeyboardButton(
                    text=display_text,
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

    elif action == "users":
        users = await db.get_all_users(50)

        if not users:
            await call.message.edit_text(
                "📭 Hozircha foydalanuvchilar yo'q.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                    ]
                )
            )
            return

        user_list = []
        for i, user in enumerate(users[:20], 1):
            name = user.get('first_name', 'Noma\'lum')
            last_name = f" {user.get('last_name', '')}" if user.get('last_name') else ""
            username = user.get('username')
            user_id = user.get('user_id')
            total_chats = user.get('total_chats', 1)
            has_private = user.get('has_private', 0)

            user_info = f"{i}. <b>{name}{last_name}</b>"
            if username:
                user_info += f" (@{username})"
            user_info += f"\n   ID: <code>{user_id}</code>"
            user_info += f" | Chatlar: {total_chats}"
            if has_private:
                user_info += " | ✅ Start"
            else:
                user_info += " | ❌ Start"

            user_list.append(user_info)

        response = (
            f"👥 <b>FOYDALANUVCHILAR RO'YXATI</b>\n\n"
            f"Jami: {len(users)} ta foydalanuvchi\n\n"
        )

        if len(users) > 20:
            response += f"<i>Faqat oxirgi 20 ta foydalanuvchi ko'rsatilmoqda</i>\n\n"

        response += "\n\n".join(user_list)

        await call.message.edit_text(
            response,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:users")],
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]
                ]
            )
        )

    await call.answer()


# =================== KONTAKTNI KO'RSATISH ===================
@dp.callback_query(F.data.startswith("contact:"))
async def show_contact_details(call: CallbackQuery):
    """Kontakt tafsilotlarini ko'rsatish"""
    try:
        await update_user_activity(call.from_user.id, call.message.chat.id, "contact")

        if not is_allowed_chat(call.message.chat.id):
            await call.answer("❌ Ruxsat yo'q", show_alert=True)
            return

        data_parts = call.data.split(":", 2)

        if len(data_parts) < 3:
            await call.answer("❌ Format xatosi", show_alert=True)
            return

        service = data_parts[1]
        phone = data_parts[2]

        group_id = call.message.chat.id
        await db.increment_click_count(service, group_id)

        whatsapp_url = create_whatsapp_url(phone)

        buttons = [
            [
                InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back"),
                InlineKeyboardButton(text="📞 Boshqa kontaktlar", callback_data="menu:contacts")
            ]
        ]

        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        is_long_uzbek = (cleaned.startswith("+998") and len(cleaned) == 13) or \
                        (cleaned.startswith("998") and len(cleaned) == 12) or \
                        (cleaned.isdigit() and len(cleaned) == 9) or \
                        (cleaned.isdigit() and len(cleaned) == 12)

        if is_long_uzbek:
            buttons.insert(0, [
                InlineKeyboardButton(text="💬 WhatsApp ga yozish", url=whatsapp_url)
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        response = (
            f"👤 <b>{service}</b>\n\n"
            f"📞 <b>Telefon raqami:</b>\n"
            f"<a href='tel:{phone}'>{phone}</a>\n\n"
        )

        if is_long_uzbek:
            response += "<i>📱 Raqamga qo'ng'iroq qilish yoki nusxalash uchun ustiga bosing va tanlang.</i>"

        await call.message.edit_text(response, reply_markup=keyboard)
        await call.answer()

        await add_menu_to_history(call, f"contact:{service}")

    except Exception as e:
        print(f"❌ Kontakt ko'rsatish xatosi: {e}")
        await call.answer("❌ Xatolik yuz berdi", show_alert=True)


# =================== O'CHIRISH CALLBACK ===================
@dp.callback_query(F.data.startswith("delete:"))
async def handle_delete(call: CallbackQuery):
    """Kontaktni o'chirish"""
    await update_user_activity(call.from_user.id, call.message.chat.id, "delete_contact")

    if not is_allowed_chat(call.message.chat.id) or not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    service = call.data.split(":", 1)[1]
    group_id = call.message.chat.id

    try:
        success = await db.delete_contact(service, group_id)

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
    await update_user_activity(call.from_user.id, call.message.chat.id, "back")

    success = await go_back(call)
    if not success:
        await call.answer("❌ Orqaga qaytish mumkin emas", show_alert=True)


# =================== BARCHA CALLBACK QUERIES ===================
@dp.callback_query()
async def handle_all_callbacks(call: CallbackQuery):
    """Barcha callback'lar uchun umumiy handler"""
    await update_user_activity(call.from_user.id, call.message.chat.id, call.data)

    if not call.data.startswith(("menu:", "admin:", "contact:", "delete:", "back", "force_start")):
        await call.answer("⚠️ Bu tugma hozircha ishlamaydi", show_alert=True)


# =================== BARCHA XABARLAR UCHUN HANDLER ===================
@dp.message()
async def handle_all_messages(message: Message):
    """Barcha xabarlar uchun handler"""
    user_stats = await db.get_user_stats(message.from_user.id)

    if user_stats:
        await update_user_activity(message.from_user.id, message.chat.id, "message")


# =================== DEBUG HANDLER ===================
@dp.message(F.text.startswith('/'))
async def debug_handler(message: Message):
    """Debug handler - noma'lum buyruqlar uchun"""
    if not is_allowed_chat(message.chat.id):
        return

    await update_user_activity(message.from_user.id, message.chat.id, "unknown_command")

    print(f"🔴 ISHLANMAGAN BUYRUQ: '{message.text}'")
    print(f"   👤 User: {message.from_user.id}")
    print(f"   💬 Chat: {message.chat.id}")

    is_admin_user = is_admin(message.from_user.id)
    is_private = message.chat.type == ChatType.PRIVATE

    commands_list = [
        "• /start - Botni ishga tushirish",
        "• /myinfo - Mening ma'lumotlarim",
        "• /help - Bot haqida ma'lumot",
    ]

    if not is_private:
        commands_list.extend([
            "• /aloqa - Tezkor aloqa raqamlari",
            "• /top - Mashhur 8ta kontakt",
        ])

    if is_admin_user and not is_private:
        commands_list.extend([
            "• /add - Kontakt qo'shish",
            "• /delete - Kontakt o'chirish",
        ])

    commands_text = "\n".join(commands_list)

    await message.answer(
        f"❌ <b>'{message.text}' buyrug'i topilmadi!</b>\n\n"
        f"📋 <b>Mavjud buyruqlar:</b>\n{commands_text}\n\n"
        f"<i>Yoki menyu tugmalaridan foydalaning 👇</i>",
        reply_markup=create_main_menu(is_admin_user, is_private)
    )


# =================== ASOSIY FUNKSIYA ===================
async def main():
    """Asosiy bot funksiyasi"""
    print("=" * 60)
    print("🤖 MAHALLA ALOQA BOTI ISHGA TUSHMOGDA...")
    print("=" * 60)

    print_config()
    print("=" * 60)

    print("🔄 PostgreSQL database ulanmoqda...")
    db_ok = await db.init_db()
    if not db_ok:
        print("❌ Database bilan muammo! Bot ishlamaydi.")
        return

    await setup_bot_commands()

    print("✅ Bot tayyor!")
    print("=" * 60)

    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"❌ Bot xatosi: {e}")
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())