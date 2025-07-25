
import asyncio
import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import datetime

# Bot configuration
import os
TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = 7718878771

# Conversation states
ADD_USER, BLOCK_USER, SET_CHANNEL, SEND_BROADCAST, GRANT_PERMISSIONS, EDIT_TEXT = range(6)

# Bot settings
bot_settings = {
    'active': True,
    'owner_only': False,
    'allowed_users': set(),
    'blocked_users': set(),
    'total_calculations': 0,
    'user_stats': {},
    'channel_id': None,
    'channel_username': None,
    'privileged_users': set(),  # المستخدمين ذوي الصلاحيات الخاصة
    'custom_texts': {
        'welcome_message': """🤖 مرحباً بك في بوت حساب النقاط المحورية

📊 لحساب النقاط المحورية، أرسل البيانات بالتنسيق التالي:
أعلى سعر,أدنى سعر,سعر الإغلاق

مثال:
3250.75,3200.25,3225.50

🔍 سيقوم البوت بحساب:
• منطقة دخول (PP)
• الأهداف (R1, R2, R3)
• مستويات الدعم (S1, S2, S3)

💡 جميع النتائج ستظهر برقمين فقط بعد الفاصلة العشرية""",
        'channel_recommendation_header': "🔔 توصية جديدة - تحليل النقاط المحورية",
        'custom_recommendation_header': "🔥 توصية جديدة - طريقة دخول خاصة",
        'scalp_footer': "⚡ نوع التداول: سكالبينغ (دخول وخروج سريع)",
        'swing_footer': "📊 نوع التداول: سوينغ (صبر على الأهداف)",
        'help_message': """📚 دليل الاستخدام

🔢 تنسيق البيانات:
أرسل البيانات بالتنسيق التالي:
أعلى سعر,أدنى سعر,سعر الإغلاق

📝 أمثلة صحيحة:
• 3250.75,3200.25,3225.50
• 1850,1820,1835
• 50.25,49.80,50.10

⚠️ ملاحظات مهمة:
• استخدم الفاصلة (,) للفصل بين القيم
• أعلى سعر يجب أن يكون >= أدنى سعر
• يمكن استخدام الأرقام العشرية أو الصحيحة

📊 النتائج:
• جميع النتائج تظهر برقمين فقط بعد الفاصلة
• يتم حساب 7 مستويات: منطقة دخول (PP), الأهداف (R1, R2, R3), الدعم (S1, S2, S3)"""
    }
}

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Settings file path
SETTINGS_FILE = "bot_settings.json"

def save_settings():
    """Save bot settings to file"""
    try:
        settings_to_save = bot_settings.copy()
        settings_to_save['allowed_users'] = list(bot_settings['allowed_users'])
        settings_to_save['blocked_users'] = list(bot_settings['blocked_users'])
        settings_to_save['privileged_users'] = list(bot_settings['privileged_users'])

        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_to_save, f, ensure_ascii=False, indent=2)
        logger.info("Settings saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

def load_settings():
    """Load bot settings from file"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)

            if 'allowed_users' in loaded_settings:
                loaded_settings['allowed_users'] = set(loaded_settings['allowed_users'])
            if 'blocked_users' in loaded_settings:
                loaded_settings['blocked_users'] = set(loaded_settings['blocked_users'])
            if 'privileged_users' in loaded_settings:
                loaded_settings['privileged_users'] = set(loaded_settings['privileged_users'])

            for key, value in loaded_settings.items():
                if key in bot_settings:
                    bot_settings[key] = value

            logger.info("Settings loaded successfully")
            return True
        else:
            logger.info("Settings file not found, using default settings")
            return False
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return False

def auto_save():
    """Auto save settings after any change"""
    save_settings()

def is_owner(user_id):
    """Check if user is the owner"""
    return user_id == OWNER_CHAT_ID

def is_privileged(user_id):
    """Check if user has special privileges"""
    return is_owner(user_id) or user_id in bot_settings['privileged_users']

def can_use_bot(user_id):
    """Check if user can use the bot"""
    if not bot_settings['active']:
        return False

    if user_id in bot_settings['blocked_users']:
        return False

    if bot_settings['owner_only']:
        return is_owner(user_id)

    if bot_settings['allowed_users']:
        return user_id in bot_settings['allowed_users'] or is_owner(user_id)

    return True

def update_user_stats(user_id, username, first_name=None):
    """Update user statistics"""
    if user_id not in bot_settings['user_stats']:
        bot_settings['user_stats'][user_id] = {
            'username': username,
            'first_name': first_name,
            'calculations': 0,
            'first_use': datetime.datetime.now().isoformat()
        }
    else:
        bot_settings['user_stats'][user_id]['username'] = username
        if first_name:
            bot_settings['user_stats'][user_id]['first_name'] = first_name

    bot_settings['user_stats'][user_id]['calculations'] += 1
    bot_settings['total_calculations'] += 1

def calculate_pivot_points(high, low, close):
    """Calculate pivot points using classic formula"""
    pivot = (high + low + close) / 3

    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)

    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)

    return {
        'pivot': round(pivot, 2),
        'r1': round(r1, 2),
        'r2': round(r2, 2),
        'r3': round(r3, 2),
        's1': round(s1, 2),
        's2': round(s2, 2),
        's3': round(s3, 2)
    }

def format_results(results):
    """Format the results in a professional way"""
    message = "📊 تحليل النقاط المحورية\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    message += f"🎯 الأهداف (مستويات المقاومة):\n"
    message += f"الهدف الثالث: {results['r3']:.2f}\n"
    message += f"الهدف الثاني: {results['r2']:.2f}\n"
    message += f"الهدف الأول: {results['r1']:.2f}\n\n"

    message += f"🚪 منطقة دخول:\n"
    message += f"PP: {results['pivot']:.2f}\n\n"

    message += f"🛡️ مستويات الدعم:\n"
    message += f"S1: {results['s1']:.2f}\n"
    message += f"S2: {results['s2']:.2f}\n"
    message += f"S3: {results['s3']:.2f}\n\n"

    message += "━━━━━━━━━━━━━━━━━━━━━━\n"
    message += "📈 تم الحساب باستخدام الصيغة الكلاسيكية"

    return message

def format_channel_recommendation(results, high, low, close):
    """Format recommendation message for channel"""
    message = f"{bot_settings['custom_texts']['channel_recommendation_header']}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if close > results['pivot']:
        recommendation = "📈 شراء (BUY)"
        entry_zone = f"{results['pivot']:.2f} - {results['s1']:.2f}"
        targets = f"🎯 الأهداف:\nTP1: {results['r1']:.2f}\nTP2: {results['r2']:.2f}\nTP3: {results['r3']:.2f}"
        stop_loss = f"🛑 وقف الخسارة: {results['s2']:.2f}"
        
        # إضافة توصيات السكالبينغ والسوينغ
        scalp_target = f"⚡ سكالبينغ: {results['r1']:.2f}"
        swing_target = f"📊 سوينغ: {results['r2']:.2f} - {results['r3']:.2f}"
    else:
        recommendation = "📉 بيع (SELL)"
        entry_zone = f"{results['pivot']:.2f} - {results['r1']:.2f}"
        targets = f"🎯 الأهداف:\nTP1: {results['s1']:.2f}\nTP2: {results['s2']:.2f}\nTP3: {results['s3']:.2f}"
        stop_loss = f"🛑 وقف الخسارة: {results['r2']:.2f}"
        
        # إضافة توصيات السكالبينغ والسوينغ
        scalp_target = f"⚡ سكالبينغ: {results['s1']:.2f}"
        swing_target = f"📊 سوينغ: {results['s2']:.2f} - {results['s3']:.2f}"

    message += f"{recommendation}\n\n"
    message += f"🔴 منطقة الدخول: {entry_zone}\n\n"
    message += f"{targets}\n\n"
    message += f"{stop_loss}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"{scalp_target}\n"
    message += f"{swing_target}\n\n"
    message += "⚠️ تداول بحذر وأدر المخاطر بحكمة"

    return message

def format_custom_recommendation(results, high, low, close, trade_type):
    """Format custom recommendation message for channel (scalp/swing)"""
    message = f"{bot_settings['custom_texts']['custom_recommendation_header']}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if close > results['pivot']:
        recommendation = "📈 شراء (BUY)"
        entry_zone = f"{results['pivot']:.2f} - {results['s1']:.2f}"
        targets = f"🎯 الأهداف:\nTP1: {results['r1']:.2f}\nTP2: {results['r2']:.2f}\nTP3: {results['r3']:.2f}"
        
        # حساب وقف الخسارة بحد أقصى 25 نقطة
        if trade_type == "scalp":
            # للسكالبينغ: وقف خسارة ضيق
            stop_distance = min(abs(results['pivot'] - results['s2']), 25.0)
            calculated_stop = results['pivot'] - stop_distance
        else:  # swing
            # للسوينغ: وقف خسارة أوسع قليلاً لكن ضمن 25 نقطة
            stop_distance = min(abs(results['pivot'] - results['s2']), 25.0)
            calculated_stop = results['pivot'] - stop_distance
            
    else:
        recommendation = "📉 بيع (SELL)"
        entry_zone = f"{results['pivot']:.2f} - {results['r1']:.2f}"
        targets = f"🎯 الأهداف:\nTP1: {results['s1']:.2f}\nTP2: {results['s2']:.2f}\nTP3: {results['s3']:.2f}"
        
        # حساب وقف الخسارة بحد أقصى 25 نقطة
        if trade_type == "scalp":
            # للسكالبينغ: وقف خسارة ضيق
            stop_distance = min(abs(results['r2'] - results['pivot']), 25.0)
            calculated_stop = results['pivot'] + stop_distance
        else:  # swing
            # للسوينغ: وقف خسارة أوسع قليلاً لكن ضمن 25 نقطة
            stop_distance = min(abs(results['r2'] - results['pivot']), 25.0)
            calculated_stop = results['pivot'] + stop_distance

    stop_loss = f"🛑 وقف الخسارة : {calculated_stop:.2f}"

    message += f"{recommendation}\n\n"
    message += f"🔴 منطقة الدخول: {entry_zone}\n\n"
    message += f"{targets}\n\n"
    message += f"{stop_loss}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━\n"
    message += "🫰🏻رجاءًا اقل لوت حبيبي\n\n"
    
    if trade_type == "scalp":
        message += bot_settings['custom_texts']['scalp_footer']
    else:
        message += bot_settings['custom_texts']['swing_footer']

    return message

async def send_user_notification(context, user_id, username):
    """Send user entry notification to owner"""
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    notification_message = f"👤 مستخدم جديد دخل البوت:\n"
    notification_message += f"• اليوزر: @{username}\n"
    notification_message += f"• المعرف: {user_id}\n"
    notification_message += f"• الوقت: {timestamp}"

    try:
        await context.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text=notification_message
        )
    except Exception as e:
        logger.error(f"Error sending notification to owner: {e}")

async def send_to_channel(context, message):
    """Send message to channel if configured"""
    if bot_settings['channel_id']:
        try:
            logger.info(f"Sending message to channel: {bot_settings['channel_id']}")
            await context.bot.send_message(
                chat_id=bot_settings['channel_id'],
                text=message
            )
            logger.info("Message sent to channel successfully")
            return True
        except Exception as e:
            logger.error(f"Error sending to channel {bot_settings['channel_id']}: {e}")
            return False
    else:
        logger.info("No channel configured for recommendations")
    return False

async def broadcast_message(context, message, sender_id):
    """Send broadcast message to all users"""
    success_count = 0
    failed_count = 0

    sender_info = ""
    if sender_id == OWNER_CHAT_ID:
        sender_info = "📢 رسالة من المالك"
    else:
        sender_username = bot_settings['user_stats'].get(sender_id, {}).get('username', 'مجهول')
        sender_info = f"📢 رسالة من المشرف @{sender_username}"

    broadcast_text = f"{sender_info}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{message}\n\n━━━━━━━━━━━━━━━━━━━━━━\n⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"

    for user_id in bot_settings['user_stats'].keys():
        if user_id != sender_id:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_text
                )
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send broadcast to {user_id}: {e}")

    return success_count, failed_count

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    # Handle both message and callback query
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        username = query.from_user.username or "مجهول"
        first_name = query.from_user.first_name or "مجهول"
        is_callback = True
    else:
        user_id = update.effective_user.id
        username = update.effective_user.username or "مجهول"
        first_name = update.effective_user.first_name or "مجهول"
        is_callback = False

    if not can_use_bot(user_id):
        error_message = ("❌ عذراً، البوت غير متاح حالياً\n\n"
                        "يرجى التواصل مع مطور البوت للحصول على الإذن")
        if is_callback:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)
        return

    if not is_owner(user_id) and user_id not in bot_settings['user_stats'] and not is_callback:
        await send_user_notification(context, user_id, username)

    welcome_message = bot_settings['custom_texts']['welcome_message']

    keyboard = []

    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")])
        keyboard.append([InlineKeyboardButton("📚 قائمة الأوامر", callback_data="commands_list")])
        welcome_message += "\n\n👑 مرحباً بك أيها المالك!"
    elif is_privileged(user_id):
        keyboard.append([InlineKeyboardButton("🔧 لوحة المشرف", callback_data="supervisor_panel")])
        keyboard.append([InlineKeyboardButton("📚 قائمة الأوامر", callback_data="commands_list")])
        welcome_message += "\n\n⭐ مرحباً بك أيها المشرف!"
    else:
        keyboard.append([InlineKeyboardButton("📚 قائمة الأوامر", callback_data="commands_list")])

    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_callback:
            await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    else:
        if is_callback:
            await update.callback_query.edit_message_text(welcome_message)
        else:
            await update.message.reply_text(welcome_message)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel for owner"""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if not is_owner(user_id):
        if query:
            await query.edit_message_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        else:
            await update.message.reply_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        return

    status = "🟢 نشط" if bot_settings['active'] else "🔴 متوقف"
    access_mode = "للمالك فقط" if bot_settings['owner_only'] else f"للجميع ({len(bot_settings['allowed_users'])} مسموح)" if bot_settings['allowed_users'] else "للجميع"
    channel_status = f"@{bot_settings['channel_username']}" if bot_settings['channel_username'] else "غير محدد"

    admin_text = f"""⚙️ لوحة إدارة البوت

📊 الإحصائيات:
• حالة البوت: {status}
• نمط الوصول: {access_mode}
• قناة التوصيات: {channel_status}
• إجمالي الحسابات: {bot_settings['total_calculations']}
• عدد المستخدمين: {len(bot_settings['user_stats'])}
• المحظورين: {len(bot_settings['blocked_users'])}
• المشرفين: {len(bot_settings['privileged_users'])}

🎛️ إعدادات التحكم:"""

    keyboard = [
        [InlineKeyboardButton("🔄 تغيير حالة البوت", callback_data="toggle_bot")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("👑 إدارة الصلاحيات", callback_data="manage_permissions")],
        [InlineKeyboardButton("📢 إعداد قناة التوصيات", callback_data="setup_channel")],
        [InlineKeyboardButton("📨 إرسال رسالة جماعية", callback_data="send_broadcast")],
        [InlineKeyboardButton("📝 تحرير النصوص", callback_data="edit_texts")],
        [InlineKeyboardButton("💾 حفظ الإعدادات", callback_data="save_settings")],
        [InlineKeyboardButton("📊 الإحصائيات التفصيلية", callback_data="detailed_stats")],
        [InlineKeyboardButton("📚 قائمة الأوامر", callback_data="commands_list")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(admin_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(admin_text, reply_markup=reply_markup)

async def supervisor_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supervisor panel for privileged users"""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if not is_privileged(user_id):
        if query:
            await query.edit_message_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        else:
            await update.message.reply_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        return

    supervisor_text = f"""🔧 لوحة المشرف

📊 الإحصائيات:
• إجمالي الحسابات: {bot_settings['total_calculations']}
• عدد المستخدمين: {len(bot_settings['user_stats'])}

🎛️ الأدوات المتاحة:"""

    keyboard = [
        [InlineKeyboardButton("📢 إعداد قناة التوصيات", callback_data="setup_channel")],
        [InlineKeyboardButton("📨 إرسال رسالة جماعية", callback_data="send_broadcast")],
        [InlineKeyboardButton("📊 الإحصائيات التفصيلية", callback_data="detailed_stats")],
        [InlineKeyboardButton("📚 قائمة الأوامر", callback_data="commands_list")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(supervisor_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(supervisor_text, reply_markup=reply_markup)

async def manage_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage user permissions"""
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("❌ هذه الصفحة للمالك فقط")
        return

    text = f"""👑 إدارة الصلاحيات

المشرفين الحاليين: {len(bot_settings['privileged_users'])}

يمكن للمشرفين:
• إعداد قناة التوصيات
• إرسال رسائل جماعية
• عرض الإحصائيات"""

    keyboard = [
        [InlineKeyboardButton("➕ إضافة مشرف", callback_data="grant_permissions")],
        [InlineKeyboardButton("📋 قائمة المشرفين", callback_data="list_supervisors")],
        [InlineKeyboardButton("➖ إزالة مشرف", callback_data="revoke_permissions")],
        [InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="admin_panel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def list_supervisors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all supervisors"""
    query = update.callback_query
    await query.answer()

    if not bot_settings['privileged_users']:
        text = "📋 قائمة المشرفين\n\n❌ لا يوجد مشرفين حالياً"
    else:
        text = "📋 قائمة المشرفين:\n\n"
        for user_id in bot_settings['privileged_users']:
            if user_id in bot_settings['user_stats']:
                username = bot_settings['user_stats'][user_id]['username']
                first_name = bot_settings['user_stats'][user_id].get('first_name', 'مجهول')
                text += f"• @{username} ({first_name}) - ID: {user_id}\n"
            else:
                text += f"• ID: {user_id}\n"

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="manage_permissions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def revoke_permissions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu to revoke permissions"""
    query = update.callback_query
    await query.answer()

    if not bot_settings['privileged_users']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="manage_permissions")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ لا يوجد مشرفين لإزالتهم!",
            reply_markup=reply_markup
        )
        return

    text = "➖ إزالة مشرف\n\nاختر المشرف المراد إزالته:\n"
    keyboard = []

    for user_id in list(bot_settings['privileged_users'])[:10]:
        if user_id in bot_settings['user_stats']:
            username = bot_settings['user_stats'][user_id]['username']
            text += f"• @{username} (ID: {user_id})\n"
            keyboard.append([InlineKeyboardButton(f"إزالة @{username}", callback_data=f"revoke_{user_id}")])
        else:
            text += f"• ID: {user_id}\n"
            keyboard.append([InlineKeyboardButton(f"إزالة {user_id}", callback_data=f"revoke_{user_id}")])

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_permissions")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)

async def setup_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Setup channel menu"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_privileged(user_id):
        await query.edit_message_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        return

    current_channel = f"@{bot_settings['channel_username']}" if bot_settings['channel_username'] else "غير محدد"

    text = f"""📢 إعدادات قناة التوصيات

القناة الحالية: {current_channel}

ℹ️ عند ربط قناة، سيتم إرسال جميع التوصيات المحسوبة إليها تلقائياً مع تنسيق خاص للقناة."""

    keyboard = [
        [InlineKeyboardButton("➕ إضافة/تغيير القناة", callback_data="add_channel")],
        [InlineKeyboardButton("❌ حذف القناة", callback_data="remove_channel")],
    ]

    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="admin_panel")])
    else:
        keyboard.append([InlineKeyboardButton("🔙 رجوع للوحة المشرف", callback_data="supervisor_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def send_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast message conversation"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_privileged(user_id):
        await query.edit_message_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        return

    await query.edit_message_text(
        "📨 إرسال رسالة جماعية\n\n"
        "اكتب الرسالة التي تريد إرسالها لجميع المستخدمين:\n\n"
        "💡 نصائح:\n"
        "• اكتب رسالة واضحة ومفيدة\n"
        "• تجنب الرسائل الطويلة جداً\n"
        "• سيتم إضافة معلومات المرسل تلقائياً\n\n"
        "أو أرسل /cancel للإلغاء"
    )

    return SEND_BROADCAST

async def send_broadcast_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process broadcast message"""
    user_id = update.effective_user.id

    if not is_privileged(user_id):
        await update.message.reply_text("❌ غير مسموح لك بهذه العملية")
        return ConversationHandler.END

    message = update.message.text.strip()

    if len(message) > 4000:
        await update.message.reply_text(
            "❌ الرسالة طويلة جداً!\n\n"
            "الحد الأقصى 4000 حرف.\n"
            "أعد كتابة رسالة أقصر أو أرسل /cancel للإلغاء"
        )
        return SEND_BROADCAST

    keyboard = [
        [InlineKeyboardButton("✅ تأكيد الإرسال", callback_data=f"confirm_broadcast_{user_id}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.user_data['broadcast_message'] = message

    await update.message.reply_text(
        f"📨 معاينة الرسالة:\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{message}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"سيتم إرسالها لـ {len(bot_settings['user_stats'])} مستخدم\n\n"
        f"هل تريد المتابعة؟",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and send broadcast"""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[2])

    if query.from_user.id != user_id:
        await query.edit_message_text("❌ خطأ في التحقق")
        return

    message = context.user_data.get('broadcast_message')
    if not message:
        await query.edit_message_text("❌ لم يتم العثور على الرسالة")
        return

    await query.edit_message_text("⏳ جارٍ إرسال الرسالة...")
    success_count, failed_count = await broadcast_message(context, message, user_id)

    result_text = f"✅ تم إرسال الرسالة!\n\n"
    result_text += f"📊 النتائج:\n"
    result_text += f"• تم الإرسال بنجاح: {success_count}\n"
    result_text += f"• فشل الإرسال: {failed_count}\n"
    result_text += f"• المجموع: {success_count + failed_count}"

    keyboard = []
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="admin_panel")])
    else:
        keyboard.append([InlineKeyboardButton("🔙 رجوع للوحة المشرف", callback_data="supervisor_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(result_text, reply_markup=reply_markup)

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel broadcast"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    keyboard = []

    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="admin_panel")])
    else:
        keyboard.append([InlineKeyboardButton("🔙 رجوع للوحة المشرف", callback_data="supervisor_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("❌ تم إلغاء إرسال الرسالة", reply_markup=reply_markup)

async def grant_permissions_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start granting permissions conversation"""
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("❌ هذه الصفحة للمالك فقط")
        return

    await query.edit_message_text(
        "👑 إضافة مشرف جديد\n\n"
        "أرسل معرف المستخدم (User ID) الذي تريد منحه صلاحيات الإشراف:\n\n"
        "مثال: 123456789\n\n"
        "💡 المشرف سيتمكن من:\n"
        "• إعداد قناة التوصيات\n"
        "• إرسال رسائل جماعية\n"
        "• عرض الإحصائيات\n\n"
        "أو أرسل /cancel للإلغاء"
    )

    return GRANT_PERMISSIONS

async def grant_permissions_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process granting permissions"""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ غير مسموح لك بهذه العملية")
        return ConversationHandler.END

    try:
        user_id = int(update.message.text.strip())

        if user_id == OWNER_CHAT_ID:
            await update.message.reply_text("❌ المالك لديه جميع الصلاحيات بالفعل!")
            return GRANT_PERMISSIONS

        if user_id in bot_settings['privileged_users']:
            await update.message.reply_text("❌ هذا المستخدم مشرف بالفعل!")
            return GRANT_PERMISSIONS

        bot_settings['privileged_users'].add(user_id)
        auto_save()

        keyboard = [[InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="manage_permissions")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        user_info = ""
        if user_id in bot_settings['user_stats']:
            username = bot_settings['user_stats'][user_id]['username']
            user_info = f" (@{username})"

        await update.message.reply_text(
            f"✅ تم منح صلاحيات الإشراف للمستخدم {user_id}{user_info} بنجاح!\n\n"
            "يمكنه الآن:\n"
            "• إعداد قناة التوصيات\n"
            "• إرسال رسائل جماعية\n"
            "• عرض الإحصائيات\n\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=reply_markup
        )

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ معرف المستخدم غير صحيح!\n\n"
            "يرجى إرسال رقم صحيح أو /cancel للإلغاء"
        )
        return GRANT_PERMISSIONS

async def set_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start setting channel conversation"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_privileged(user_id):
        await query.edit_message_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        return

    await query.edit_message_text(
        "📢 إضافة قناة التوصيات\n\n"
        "أرسل معرف القناة أو يوزرها:\n\n"
        "أمثلة:\n"
        "• @channel_username\n"
        "• https://t.me/channel_username\n"
        "• -1001234567890\n\n"
        "⚠️ تأكد من:\n"
        "• إضافة البوت كمشرف في القناة\n"
        "• منح البوت صلاحية الإرسال\n\n"
        "أو أرسل /cancel للإلغاء"
    )

    return SET_CHANNEL

async def set_channel_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process setting channel"""
    user_id = update.effective_user.id

    if not is_privileged(user_id):
        await update.message.reply_text("❌ غير مسموح لك بهذه العملية")
        return ConversationHandler.END

    channel_input = update.message.text.strip()

    if channel_input.startswith('https://t.me/'):
        channel_username = channel_input.replace('https://t.me/', '').split('?')[0]
    elif channel_input.startswith('https://telegram.me/'):
        channel_username = channel_input.replace('https://telegram.me/', '').split('?')[0]
    elif channel_input.startswith('@'):
        channel_username = channel_input[1:]
    else:
        channel_username = channel_input

    channel_username = channel_username.strip()

    try:
        chat_id = None
        chat_title = "Unknown"
        chat_type = "Unknown"

        try:
            chat = await context.bot.get_chat(f"@{channel_username}")
            chat_id = chat.id
            chat_title = chat.title or channel_username
            chat_type = chat.type
        except:
            try:
                chat = await context.bot.get_chat(channel_username)
                chat_id = chat.id
                chat_title = chat.title or channel_username
                chat_type = chat.type
            except:
                if channel_username.isdigit() or channel_username.startswith('-'):
                    try:
                        chat = await context.bot.get_chat(int(channel_username))
                        chat_id = chat.id
                        chat_title = chat.title or str(channel_username)
                        chat_type = chat.type
                    except:
                        pass

        if not chat_id:
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="setup_channel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"❌ لم يتم العثور على القناة: {channel_username}\n\n"
                "تأكد من:\n"
                "• صحة يوزر القناة\n"
                "• أن القناة عامة أو البوت عضو فيها\n"
                "• إضافة البوت كأدمن في القناة\n\n"
                "أعد المحاولة أو أرسل /cancel للإلغاء",
                reply_markup=reply_markup
            )
            return SET_CHANNEL

        try:
            test_message = await context.bot.send_message(
                chat_id=chat_id,
                text="🤖 تم ربط البوت بهذه القناة بنجاح!\nسيتم حذف هذه الرسالة خلال 5 ثوان."
            )
            await asyncio.sleep(5)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=test_message.message_id)
            except:
                pass
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="setup_channel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"❌ البوت لا يستطيع الإرسال في هذه القناة!\n\n"
                "تأكد من:\n"
                "• إضافة البوت كأدمن\n"
                "• منح البوت صلاحية الإرسال\n\n"
                f"خطأ: {str(e)[:100]}\n\n"
                "أعد المحاولة أو أرسل /cancel للإلغاء",
                reply_markup=reply_markup
            )
            return SET_CHANNEL

        bot_settings['channel_id'] = chat_id
        bot_settings['channel_username'] = channel_username
        auto_save()

        keyboard = []
        if is_owner(user_id):
            keyboard.append([InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="setup_channel")])
        else:
            keyboard.append([InlineKeyboardButton("🔙 رجوع للوحة المشرف", callback_data="setup_channel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ تم ربط القناة بنجاح!\n\n"
            f"القناة: @{channel_username}\n"
            f"العنوان: {chat_title}\n"
            f"النوع: {chat_type}\n"
            f"المعرف: {chat_id}\n\n"
            "سيتم إرسال جميع التوصيات لهذه القناة تلقائياً.\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=reply_markup
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error setting channel: {e}")
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="setup_channel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"❌ خطأ في ربط القناة!\n\n"
            "تأكد من صحة البيانات والأذونات\n\n"
            "أعد المحاولة أو أرسل /cancel للإلغاء",
            reply_markup=reply_markup
        )
        return SET_CHANNEL

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any conversation"""
    user_id = update.effective_user.id
    keyboard = []

    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="admin_panel")])
    elif is_privileged(user_id):
        keyboard.append([InlineKeyboardButton("🔙 رجوع للوحة المشرف", callback_data="supervisor_panel")])
    else:
        keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "❌ تم إلغاء العملية",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle price input and calculate pivot points"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name

    if not can_use_bot(user_id):
        if not bot_settings['active']:
            await update.message.reply_text("🔴 البوت متوقف حالياً من قبل الإدارة")
        elif user_id in bot_settings['blocked_users']:
            await update.message.reply_text("🚫 تم حظرك من استخدام البوت")
        elif bot_settings['owner_only']:
            await update.message.reply_text("👑 البوت متاح للمالك فقط حالياً")
        else:
            await update.message.reply_text("❌ غير مسموح لك باستخدام البوت")
        return

    try:
        text = update.message.text.strip()
        prices = text.split(',')

        if len(prices) != 3:
            await update.message.reply_text(
                "❌ خطأ في التنسيق\n\n"
                "يرجى إرسال البيانات بالتنسيق التالي:\n"
                "أعلى سعر,أدنى سعر,سعر الإغلاق\n\n"
                "مثال: 3250.75,3200.25,3225.50"
            )
            return

        high = float(prices[0].strip())
        low = float(prices[1].strip())
        close = float(prices[2].strip())

        if high < low:
            await update.message.reply_text(
                "❌ خطأ في البيانات\n\n"
                "أعلى سعر يجب أن يكون أكبر من أو يساوي أدنى سعر"
            )
            return

        results = calculate_pivot_points(high, low, close)
        update_user_stats(user_id, username, first_name)
        auto_save()

        message = format_results(results)
        await update.message.reply_text(message)

        # Send to channel if configured
        if bot_settings['channel_id']:
            channel_message = format_channel_recommendation(results, high, low, close)
            channel_sent = await send_to_channel(context, channel_message)
            if channel_sent:
                await update.message.reply_text("📢 تم إرسال التوصية للقناة أيضاً!")
            else:
                logger.warning("Failed to send recommendation to channel")

        logger.info(f"Calculated pivot points for user {user_id} - H:{high}, L:{low}, C:{close}")

    except ValueError:
        await update.message.reply_text(
            "❌ خطأ في البيانات\n\n"
            "يرجى التأكد من إدخال أرقام صحيحة فقط\n\n"
            "مثال: 3250.75,3200.25,3225.50"
        )
    except Exception as e:
        logger.error(f"Error in calculation: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ غير متوقع\n\n"
            "يرجى المحاولة مرة أخرى أو التواصل مع المطور"
        )

async def pivot_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pivot points guide"""
    query = update.callback_query
    await query.answer()

    guide_text = """📊 دليل النقاط المحورية

🎯 كيفية الاستخدام:
أرسل البيانات بالتنسيق:
أعلى سعر,أدنى سعر,سعر الإغلاق

📝 مثال: 3250.75,3200.25,3225.50

🔢 النتائج:
• PP (النقطة المحورية) - منطقة الدخول
• R1, R2, R3 - مستويات المقاومة (أهداف)
• S1, S2, S3 - مستويات الدعم (وقف خسارة)

📈 استراتيجية الاستخدام:
• إذا كان السعر فوق PP = شراء
• إذا كان السعر تحت PP = بيع
• الأهداف: R1, R2, R3 للشراء
• الأهداف: S1, S2, S3 للبيع

⚠️ نصائح مهمة:
• استخدم وقف خسارة دائماً
• لا تتداول بكامل رأس المال
• تابع الأخبار الاقتصادية"""

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(guide_text, reply_markup=reply_markup)

async def trading_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trading strategies guide"""
    query = update.callback_query
    await query.answer()

    guide_text = """📈 دليل استراتيجيات التداول

🎯 سكالبينغ (Scalping):
• المدة: 1-15 دقيقة
• الهدف: 5-15 نقطة
• وقف الخسارة: 3-8 نقاط
• أفضل الأوقات: افتتاح الأسواق

📊 سوينغ (Swing Trading):
• المدة: 1-7 أيام
• الهدف: 50-200 نقطة
• وقف الخسارة: 20-50 نقطة
• التحليل: الاتجاهات الرئيسية

💡 قواعد إدارة المخاطر:
• لا تخاطر بأكثر من 2% من رأس المال
• استخدم وقف خسارة دائماً
• لا تضاعف الخسائر
• خذ الأرباح تدريجياً

⚡ نصائح للنجاح:
• التزم بالخطة
• لا تتداول بالعاطفة
• تعلم من الأخطاء
• اصبر على الفرص الجيدة"""

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(guide_text, reply_markup=reply_markup)

async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show commands list based on user level"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not can_use_bot(user_id):
        await query.edit_message_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        return

    # Basic commands for all users
    commands_text = """📚 قائمة الأوامر المتاحة

🔧 الأوامر الأساسية:
• /start - بدء البوت والترحيب
• /help - دليل الاستخدام التفصيلي
• /signal - توصيات السكالبينغ والسوينغ
• إرسال الأرقام - حساب النقاط المحورية

📊 كيفية الاستخدام:
أرسل البيانات بالتنسيق: أعلى,أدنى,إغلاق
مثال: 3250.75,3200.25,3225.50

🎯 النتائج المحسوبة:
• منطقة دخول (PP)
• الأهداف: R1, R2, R3
• مستويات الدعم: S1, S2, S3"""

    # Add privileged commands if user has permissions
    if is_privileged(user_id):
        commands_text += """\n\n🔧 أوامر المشرفين:
• /scalp أعلى,أدنى,إغلاق - توصية سكالبينغ مخصصة
• /swing أعلى,أدنى,إغلاق - توصية سوينغ مخصصة
• لوحة المشرف - إدارة القناة والرسائل
• إعداد قناة التوصيات
• إرسال رسائل جماعية
• عرض الإحصائيات التفصيلية"""

    # Add owner commands if user is owner
    if is_owner(user_id):
        commands_text += """\n\n👑 أوامر المالك:
• /admin - لوحة الإدارة الكاملة
• /scalp أعلى,أدنى,إغلاق - توصية سكالبينغ مخصصة
• /swing أعلى,أدنى,إغلاق - توصية سوينغ مخصصة
• إدارة المستخدمين (إضافة/حظر)
• إدارة الصلاحيات (منح/سحب)
• تغيير حالة البوت
• حفظ واستعادة الإعدادات
• إدارة قناة التوصيات
• إرسال رسائل جماعية
• عرض إحصائيات شاملة"""

    keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(commands_text, reply_markup=reply_markup)

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Signal command for trading recommendations"""
    user_id = update.effective_user.id

    if not can_use_bot(user_id):
        await update.message.reply_text("❌ غير مسموح لك باستخدام البوت")
        return

    if is_privileged(user_id):
        signal_message = """📊 توصيات التداول - سكالبينغ وسوينغ

🎯 للمشرفين والمالك:
• /scalp أعلى,أدنى,إغلاق - توصية سكالبينغ
• /swing أعلى,أدنى,إغلاق - توصية سوينغ

مثال: /scalp 3370,3350,3365
سيتم إرسال توصية مخصصة للقناة

🎯 سكالبينغ (Scalping):
• استراتيجية قصيرة المدى (دقائق)
• أهداف سريعة ومحدودة
• وقف خسارة ضيق (حد أقصى 25 نقطة)

📈 سوينغ (Swing Trading):
• استراتيجية متوسطة المدى (أيام/أسابيع)
• أهداف أكبر ووقت أطول
• وقف خسارة أوسع (حد أقصى 25 نقطة)

⚠️ تحذير: التداول محفوف بالمخاطر
تذكر إدارة المخاطر دائماً"""
    else:
        signal_message = """📊 توصيات التداول - سكالبينغ وسوينغ

🎯 سكالبينغ (Scalping):
• استراتيجية قصيرة المدى (دقائق)
• أهداف سريعة ومحدودة
• دخول عند كسر المقاومات أو الدعوم
• وقف خسارة ضيق

📈 سوينغ (Swing Trading):
• استراتيجية متوسطة المدى (أيام/أسابيع)
• أهداف أكبر ووقت أطول
• اعتماد على الاتجاهات الرئيسية
• وقف خسارة أوسع

💡 كيفية الاستخدام:
1. أرسل بياناتك: أعلى,أدنى,إغلاق
2. احصل على النقاط المحورية
3. استخدم المستويات للدخول والخروج

⚠️ تحذير: التداول محفوف بالمخاطر
تذكر إدارة المخاطر دائماً"""

    keyboard = [
        [InlineKeyboardButton("📊 حساب النقاط المحورية", callback_data="pivot_guide")],
        [InlineKeyboardButton("📚 دليل التداول", callback_data="trading_guide")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(signal_message, reply_markup=reply_markup)

async def scalp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scalp command for custom scalping recommendations"""
    user_id = update.effective_user.id

    if not is_privileged(user_id):
        await update.message.reply_text("❌ هذا الأمر متاح للمشرفين والمالك فقط")
        return

    if not bot_settings['channel_id']:
        await update.message.reply_text("❌ يجب إعداد قناة التوصيات أولاً!")
        return

    # Get the text after /scalp
    message_parts = update.message.text.split(' ', 1)
    if len(message_parts) < 2:
        await update.message.reply_text(
            "❌ خطأ في التنسيق\n\n"
            "الاستخدام الصحيح:\n"
            "/scalp أعلى,أدنى,إغلاق\n\n"
            "مثال: /scalp 3370.50,3350.25,3365.75"
        )
        return

    try:
        prices_text = message_parts[1].strip()
        prices = prices_text.split(',')

        if len(prices) != 3:
            await update.message.reply_text(
                "❌ خطأ في التنسيق\n\n"
                "يرجى إرسال البيانات بالتنسيق التالي:\n"
                "/scalp أعلى,أدنى,إغلاق\n\n"
                "مثال: /scalp 3370.50,3350.25,3365.75"
            )
            return

        high = float(prices[0].strip())
        low = float(prices[1].strip())
        close = float(prices[2].strip())

        if high < low:
            await update.message.reply_text("❌ أعلى سعر يجب أن يكون أكبر من أو يساوي أدنى سعر")
            return

        results = calculate_pivot_points(high, low, close)
        
        # إرسال التوصية للقناة
        channel_message = format_custom_recommendation(results, high, low, close, "scalp")
        channel_sent = await send_to_channel(context, channel_message)
        
        if channel_sent:
            await update.message.reply_text(
                f"✅ تم إرسال توصية السكالبينغ للقناة بنجاح!\n\n"
                f"📊 البيانات المستخدمة:\n"
                f"• أعلى: {high:.2f}\n"
                f"• أدنى: {low:.2f}\n"
                f"• إغلاق: {close:.2f}\n\n"
                f"⚡ نوع التوصية: سكالبينغ (دخول وخروج سريع)"
            )
        else:
            await update.message.reply_text("❌ فشل في إرسال التوصية للقناة!")

        logger.info(f"Custom scalp recommendation sent by user {user_id} - H:{high}, L:{low}, C:{close}")

    except ValueError:
        await update.message.reply_text(
            "❌ خطأ في البيانات\n\n"
            "يرجى التأكد من إدخال أرقام صحيحة فقط\n\n"
            "مثال: /scalp 3370.50,3350.25,3365.75"
        )
    except Exception as e:
        logger.error(f"Error in scalp command: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع")

async def swing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Swing command for custom swing trading recommendations"""
    user_id = update.effective_user.id

    if not is_privileged(user_id):
        await update.message.reply_text("❌ هذا الأمر متاح للمشرفين والمالك فقط")
        return

    if not bot_settings['channel_id']:
        await update.message.reply_text("❌ يجب إعداد قناة التوصيات أولاً!")
        return

    # Get the text after /swing
    message_parts = update.message.text.split(' ', 1)
    if len(message_parts) < 2:
        await update.message.reply_text(
            "❌ خطأ في التنسيق\n\n"
            "الاستخدام الصحيح:\n"
            "/swing أعلى,أدنى,إغلاق\n\n"
            "مثال: /swing 3370.50,3350.25,3365.75"
        )
        return

    try:
        prices_text = message_parts[1].strip()
        prices = prices_text.split(',')

        if len(prices) != 3:
            await update.message.reply_text(
                "❌ خطأ في التنسيق\n\n"
                "يرجى إرسال البيانات بالتنسيق التالي:\n"
                "/swing أعلى,أدنى,إغلاق\n\n"
                "مثال: /swing 3370.50,3350.25,3365.75"
            )
            return

        high = float(prices[0].strip())
        low = float(prices[1].strip())
        close = float(prices[2].strip())

        if high < low:
            await update.message.reply_text("❌ أعلى سعر يجب أن يكون أكبر من أو يساوي أدنى سعر")
            return

        results = calculate_pivot_points(high, low, close)
        
        # إرسال التوصية للقناة
        channel_message = format_custom_recommendation(results, high, low, close, "swing")
        channel_sent = await send_to_channel(context, channel_message)
        
        if channel_sent:
            await update.message.reply_text(
                f"✅ تم إرسال توصية السوينغ للقناة بنجاح!\n\n"
                f"📊 البيانات المستخدمة:\n"
                f"• أعلى: {high:.2f}\n"
                f"• أدنى: {low:.2f}\n"
                f"• إغلاق: {close:.2f}\n\n"
                f"📊 نوع التوصية: سوينغ (صبر على الأهداف)"
            )
        else:
            await update.message.reply_text("❌ فشل في إرسال التوصية للقناة!")

        logger.info(f"Custom swing recommendation sent by user {user_id} - H:{high}, L:{low}, C:{close}")

    except ValueError:
        await update.message.reply_text(
            "❌ خطأ في البيانات\n\n"
            "يرجى التأكد من إدخال أرقام صحيحة فقط\n\n"
            "مثال: /swing 3370.50,3350.25,3365.75"
        )
    except Exception as e:
        logger.error(f"Error in swing command: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    user_id = update.effective_user.id

    if not can_use_bot(user_id):
        await update.message.reply_text("❌ غير مسموح لك باستخدام البوت")
        return

    help_message = f"""{bot_settings['custom_texts']['help_message']}

🚀 الأوامر المتاحة:
• /start - بدء البوت
• /help - هذا الدليل
• /signal - توصيات السكالبينغ والسوينغ"""

    keyboard = []
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")])
    elif is_privileged(user_id):
        keyboard.append([InlineKeyboardButton("🔧 لوحة المشرف", callback_data="supervisor_panel")])
    
    keyboard.append([InlineKeyboardButton("📚 قائمة الأوامر", callback_data="commands_list")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_message, reply_markup=reply_markup)

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    query = update.callback_query
    data = query.data

    try:
        if data == "admin_panel":
            await admin_panel(update, context)
        elif data == "supervisor_panel":
            await supervisor_panel(update, context)
        elif data == "main_menu":
            await start(update, context)
        elif data == "commands_list":
            await commands_list(update, context)
        elif data == "pivot_guide":
            await pivot_guide(update, context)
        elif data == "trading_guide":
            await trading_guide(update, context)
        elif data == "manage_permissions":
            await manage_permissions(update, context)
        elif data == "setup_channel":
            await setup_channel(update, context)
        elif data == "add_channel":
            await set_channel_start(update, context)
        elif data == "send_broadcast":
            await send_broadcast_start(update, context)
        elif data == "grant_permissions":
            await grant_permissions_start(update, context)
        elif data.startswith("confirm_broadcast_"):
            await confirm_broadcast(update, context)
        elif data == "cancel_broadcast":
            await cancel_broadcast(update, context)
        elif data == "list_supervisors":
            await list_supervisors(update, context)
        elif data == "revoke_permissions":
            await revoke_permissions_menu(update, context)
        elif data.startswith("revoke_"):
            user_id = int(data.split("_")[1])
            bot_settings['privileged_users'].discard(user_id)
            auto_save()
            await query.answer("✅ تم إزالة الصلاحيات!")
            await revoke_permissions_menu(update, context)
        elif data == "edit_texts":
            await edit_texts_menu(update, context)
        elif data.startswith("edit_text_"):
            await edit_text_start(update, context)
        elif data == "toggle_bot":
            await toggle_bot(update, context)
        elif data == "manage_users":
            await manage_users(update, context)
        elif data == "detailed_stats":
            await detailed_stats(update, context)
        elif data in ["set_public", "set_owner_only", "set_inactive", "remove_channel"]:
            await handle_bot_settings(update, context)
        elif data == "list_allowed":
            await list_allowed_users(update, context)
        elif data == "list_blocked":
            await list_blocked_users(update, context)
        elif data == "unblock_user":
            await unblock_user_start(update, context)
        elif data.startswith("unblock_"):
            user_id = int(data.split("_")[1])
            bot_settings['blocked_users'].discard(user_id)
            auto_save()
            await query.answer("✅ تم إلغاء الحظر!")
            await unblock_user_start(update, context)
        elif data == "save_settings":
            await save_settings_manually(update, context)
        else:
            await query.answer("❌ خيار غير معروف")
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        await query.answer("❌ حدث خطأ, يرجى المحاولة مرة أخرى")

async def edit_texts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show text editing menu for admin"""
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("❌ هذه الصفحة للمالك فقط")
        return

    text = """📝 تحرير نصوص البوت

يمكنك تخصيص النصوص التالية:"""

    keyboard = [
        [InlineKeyboardButton("🤖 رسالة الترحيب", callback_data="edit_text_welcome_message")],
        [InlineKeyboardButton("📊 عنوان توصيات القناة", callback_data="edit_text_channel_recommendation_header")],
        [InlineKeyboardButton("🔥 عنوان التوصيات المخصصة", callback_data="edit_text_custom_recommendation_header")],
        [InlineKeyboardButton("⚡ نص السكالبينغ", callback_data="edit_text_scalp_footer")],
        [InlineKeyboardButton("📈 نص السوينغ", callback_data="edit_text_swing_footer")],
        [InlineKeyboardButton("📚 رسالة المساعدة", callback_data="edit_text_help_message")],
        [InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="admin_panel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing text conversation"""
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("❌ هذه الصفحة للمالك فقط")
        return

    text_key = query.data.replace("edit_text_", "")
    context.user_data['editing_text_key'] = text_key

    text_names = {
        'welcome_message': 'رسالة الترحيب',
        'channel_recommendation_header': 'عنوان توصيات القناة',
        'custom_recommendation_header': 'عنوان التوصيات المخصصة',
        'scalp_footer': 'نص السكالبينغ',
        'swing_footer': 'نص السوينغ',
        'help_message': 'رسالة المساعدة'
    }

    current_text = bot_settings['custom_texts'].get(text_key, '')

    await query.edit_message_text(
        f"📝 تحرير {text_names.get(text_key, text_key)}\n\n"
        f"النص الحالي:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{current_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"أرسل النص الجديد أو /cancel للإلغاء"
    )

    return EDIT_TEXT

async def edit_text_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text editing"""
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await update.message.reply_text("❌ غير مسموح لك بهذه العملية")
        return ConversationHandler.END

    text_key = context.user_data.get('editing_text_key')
    if not text_key:
        await update.message.reply_text("❌ خطأ في النظام")
        return ConversationHandler.END

    new_text = update.message.text.strip()

    if len(new_text) > 4000:
        await update.message.reply_text(
            "❌ النص طويل جداً!\n\n"
            "الحد الأقصى 4000 حرف.\n"
            "أعد كتابة نص أقصر أو أرسل /cancel للإلغاء"
        )
        return EDIT_TEXT

    bot_settings['custom_texts'][text_key] = new_text
    auto_save()

    text_names = {
        'welcome_message': 'رسالة الترحيب',
        'channel_recommendation_header': 'عنوان توصيات القناة',
        'custom_recommendation_header': 'عنوان التوصيات المخصصة',
        'scalp_footer': 'نص السكالبينغ',
        'swing_footer': 'نص السوينغ',
        'help_message': 'رسالة المساعدة'
    }

    keyboard = [[InlineKeyboardButton("🔙 رجوع لتحرير النصوص", callback_data="edit_texts")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ تم تحديث {text_names.get(text_key, text_key)} بنجاح!\n\n"
        f"النص الجديد:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{new_text[:200]}{'...' if len(new_text) > 200 else ''}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💾 تم حفظ الإعدادات تلقائياً",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

async def toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle bot status"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🟢 تفعيل للجميع", callback_data="set_public")],
        [InlineKeyboardButton("👑 للمالك فقط", callback_data="set_owner_only")],
        [InlineKeyboardButton("🔴 إيقاف البوت", callback_data="set_inactive")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🎛️ اختر نمط تشغيل البوت:\n\n"
        "🟢 للجميع: يمكن لأي شخص استخدام البوت\n"
        "👑 للمالك فقط: البوت متاح لك فقط\n"
        "🔴 إيقاف: البوت متوقف للجميع",
        reply_markup=reply_markup
    )

async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage users access"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("➕ إضافة مستخدم", callback_data="add_user")],
        [InlineKeyboardButton("➖ حظر مستخدم", callback_data="block_user")],
        [InlineKeyboardButton("📋 قائمة المسموحين", callback_data="list_allowed")],
        [InlineKeyboardButton("🚫 قائمة المحظورين", callback_data="list_blocked")],
        [InlineKeyboardButton("🔄 إلغاء حظر مستخدم", callback_data="unblock_user")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "👥 إدارة المستخدمين\n\n"
        "يمكنك التحكم في من يستطيع استخدام البوت:",
        reply_markup=reply_markup
    )

async def detailed_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed statistics"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_privileged(user_id):
        await query.edit_message_text("❌ غير مسموح لك بالوصول لهذه الصفحة")
        return

    stats_text = f"📊 الإحصائيات التفصيلية\n"
    stats_text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    stats_text += f"📈 إجمالي الحسابات: {bot_settings['total_calculations']}\n"
    stats_text += f"👥 عدد المستخدمين: {len(bot_settings['user_stats'])}\n"
    stats_text += f"✅ المسموحين: {len(bot_settings['allowed_users'])}\n"
    stats_text += f"🚫 المحظورين: {len(bot_settings['blocked_users'])}\n"
    stats_text += f"👑 المشرفين: {len(bot_settings['privileged_users'])}\n\n"

    if bot_settings['user_stats']:
        sorted_users = sorted(
            bot_settings['user_stats'].items(),
            key=lambda x: x[1]['calculations'],
            reverse=True
        )[:5]

        stats_text += "🏆 أكثر المستخدمين نشاطاً:\n"
        for i, (user_id_stat, data) in enumerate(sorted_users, 1):
            username = data['username'] or f"User_{user_id_stat}"
            stats_text += f"{i}. @{username}: {data['calculations']} حساب\n"

    keyboard = []
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    else:
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="supervisor_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(stats_text, reply_markup=reply_markup)

async def save_settings_manually(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually save settings"""
    query = update.callback_query
    await query.answer()

    success = save_settings()

    if success:
        message = "✅ تم حفظ جميع الإعدادات بنجاح!\n\n"
        message += "📋 الإعدادات المحفوظة:\n"
        message += f"• حالة البوت: {'🟢 نشط' if bot_settings['active'] else '🔴 متوقف'}\n"
        message += f"• نمط الوصول: {'للمالك فقط' if bot_settings['owner_only'] else 'للجميع'}\n"
        message += f"• المسموحين: {len(bot_settings['allowed_users'])}\n"
        message += f"• المحظورين: {len(bot_settings['blocked_users'])}\n"
        message += f"• المشرفين: {len(bot_settings['privileged_users'])}\n"
        message += f"• إجمالي الحسابات: {bot_settings['total_calculations']}\n"
        message += f"• عدد المستخدمين: {len(bot_settings['user_stats'])}\n\n"
        message += "🔄 الآن عند إعادة تشغيل البوت ستبقى جميع الإعدادات محفوظة"
    else:
        message = "❌ فشل في حفظ الإعدادات!\n\n"
        message += "يرجى المحاولة مرة أخرى أو مراجعة سجل الأخطاء"

    keyboard = [[InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)

async def list_allowed_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List allowed users"""
    query = update.callback_query
    await query.answer()

    if not bot_settings['allowed_users']:
        text = "📋 قائمة المستخدمين المسموحين\n\n❌ لا يوجد مستخدمين مسموحين حالياً"
    else:
        text = "📋 قائمة المستخدمين المسموحين:\n\n"
        for user_id in bot_settings['allowed_users']:
            if user_id in bot_settings['user_stats']:
                username = bot_settings['user_stats'][user_id]['username']
                text += f"• @{username} (ID: {user_id})\n"
            else:
                text += f"• ID: {user_id}\n"

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="manage_users")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def list_blocked_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List blocked users"""
    query = update.callback_query
    await query.answer()

    if not bot_settings['blocked_users']:
        text = "🚫 قائمة المستخدمين المحظورين\n\n❌ لا يوجد مستخدمين محظورين حالياً"
    else:
        text = "🚫 قائمة المستخدمين المحظورين:\n\n"
        for user_id in bot_settings['blocked_users']:
            if user_id in bot_settings['user_stats']:
                username = bot_settings['user_stats'][user_id]['username']
                text += f"• @{username} (ID: {user_id})\n"
            else:
                text += f"• ID: {user_id}\n"

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="manage_users")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def handle_bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bot settings changes"""
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "set_public":
        bot_settings['active'] = True
        bot_settings['owner_only'] = False
        bot_settings['allowed_users'].clear()
        auto_save()
        await query.edit_message_text(
            "✅ تم تفعيل البوت للجميع بنجاح!\n\n"
            "يمكن لأي شخص استخدام البوت الآن.\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )

    elif action == "set_owner_only":
        bot_settings['active'] = True
        bot_settings['owner_only'] = True
        auto_save()
        await query.edit_message_text(
            "👑 تم تعيين البوت للمالك فقط!\n\n"
            "أنت الوحيد الذي يمكنه استخدام البوت الآن.\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )

    elif action == "set_inactive":
        bot_settings['active'] = False
        auto_save()
        await query.edit_message_text(
            "🔴 تم إيقاف البوت!\n\n"
            "البوت متوقف للجميع حالياً.\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )

    elif action == "remove_channel":
        bot_settings['channel_id'] = None
        bot_settings['channel_username'] = None
        auto_save()

        await query.edit_message_text(
            "✅ تم حذف قناة التوصيات!\n\n"
            "لن يتم إرسال التوصيات للقناة بعد الآن.\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="setup_channel")]])
        )

async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding user conversation"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "➕ إضافة مستخدم جديد\n\n"
        "أرسل معرف المستخدم (User ID) الذي تريد إضافته:\n\n"
        "مثال: 123456789\n\n"
        "أو أرسل /cancel للإلغاء"
    )

    return ADD_USER

async def add_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process adding user"""
    try:
        user_id = int(update.message.text.strip())
        bot_settings['allowed_users'].add(user_id)

        if user_id in bot_settings['blocked_users']:
            bot_settings['blocked_users'].remove(user_id)

        auto_save()

        keyboard = [[InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="manage_users")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ تم إضافة المستخدم {user_id} بنجاح!\n\n"
            "يمكنه الآن استخدام البوت.\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=reply_markup
        )

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ معرف المستخدم غير صحيح!\n\n"
            "يرجى إرسال رقم صحيح أو /cancel للإلغاء"
        )
        return ADD_USER

async def block_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start blocking user conversation"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "➖ حظر مستخدم\n\n"
        "أرسل معرف المستخدم (User ID) الذي تريد حظره:\n\n"
        "مثال: 123456789\n\n"
        "أو أرسل /cancel للإلغاء"
    )

    return BLOCK_USER

async def block_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process blocking user"""
    try:
        user_id = int(update.message.text.strip())

        if user_id == OWNER_CHAT_ID:
            await update.message.reply_text("❌ لا يمكن حظر المالك!")
            return BLOCK_USER

        bot_settings['blocked_users'].add(user_id)

        if user_id in bot_settings['allowed_users']:
            bot_settings['allowed_users'].remove(user_id)

        if user_id in bot_settings['privileged_users']:
            bot_settings['privileged_users'].remove(user_id)

        auto_save()

        keyboard = [[InlineKeyboardButton("🔙 رجوع للإدارة", callback_data="manage_users")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ تم حظر المستخدم {user_id} بنجاح!\n\n"
            "لن يتمكن من استخدام البوت.\n"
            "💾 تم حفظ الإعدادات تلقائياً",
            reply_markup=reply_markup
        )

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ معرف المستخدم غير صحيح!\n\n"
            "يرجى إرسال رقم صحيح أو /cancel للإلغاء"
        )
        return BLOCK_USER

async def unblock_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start unblocking user"""
    query = update.callback_query
    await query.answer()

    if not bot_settings['blocked_users']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="manage_users")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ لا يوجد مستخدمين محظورين!",
            reply_markup=reply_markup
        )
        return

    text = "🔄 إلغاء حظر مستخدم\n\nالمستخدمين المحظورين:\n"
    keyboard = []

    for user_id in list(bot_settings['blocked_users'])[:10]:
        if user_id in bot_settings['user_stats']:
            username = bot_settings['user_stats'][user_id]['username']
            text += f"• @{username} (ID: {user_id})\n"
            keyboard.append([InlineKeyboardButton(f"إلغاء حظر @{username}", callback_data=f"unblock_{user_id}")])
        else:
            text += f"• ID: {user_id}\n"
            keyboard.append([InlineKeyboardButton(f"إلغاء حظر {user_id}", callback_data=f"unblock_{user_id}")])

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_users")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)

def main():
    """Main function to run the bot"""
    try:
        load_settings()
        application = Application.builder().token(BOT_TOKEN).build()

        # Conversation handlers
        add_user_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(add_user_start, pattern="^add_user$")],
            states={
                ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_process)]
            },
            fallbacks=[CommandHandler("cancel", cancel_conversation)]
        )

        block_user_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(block_user_start, pattern="^block_user$")],
            states={
                BLOCK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_user_process)]
            },
            fallbacks=[CommandHandler("cancel", cancel_conversation)]
        )

        set_channel_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(set_channel_start, pattern="^add_channel$")],
            states={
                SET_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_channel_process)]
            },
            fallbacks=[CommandHandler("cancel", cancel_conversation)]
        )

        broadcast_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(send_broadcast_start, pattern="^send_broadcast$")],
            states={
                SEND_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast_process)]
            },
            fallbacks=[CommandHandler("cancel", cancel_conversation)]
        )

        grant_permissions_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(grant_permissions_start, pattern="^grant_permissions$")],
            states={
                GRANT_PERMISSIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, grant_permissions_process)]
            },
            fallbacks=[CommandHandler("cancel", cancel_conversation)]
        )

        edit_text_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(edit_text_start, pattern="^edit_text_")],
            states={
                EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text_process)]
            },
            fallbacks=[CommandHandler("cancel", cancel_conversation)]
        )

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("signal", signal_command))
        application.add_handler(CommandHandler("scalp", scalp_command))
        application.add_handler(CommandHandler("swing", swing_command))
        application.add_handler(CommandHandler("admin", admin_panel))
        application.add_handler(add_user_handler)
        application.add_handler(block_user_handler)
        application.add_handler(set_channel_handler)
        application.add_handler(broadcast_handler)
        application.add_handler(grant_permissions_handler)
        application.add_handler(edit_text_handler)
        application.add_handler(CallbackQueryHandler(handle_callbacks))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, calculate))

        # Run the bot
        print("🤖 بوت النقاط المحورية يعمل الآن...")
        print("📊 البوت جاهز لاستقبال البيانات...")
        print(f"👑 المالك: {OWNER_CHAT_ID}")
        print("✨ المميزات المتاحة:")
        print("   - إدارة المستخدمين")
        print("   - إحصائيات تفصيلية")
        print("   - حفظ تلقائي للإعدادات")
        print("   - إشعارات المالك للمستخدمين الجدد")
        print("   - ربط قناة التوصيات")
        print("   - نظام صلاحيات المشرفين")
        print("   - إرسال رسائل جماعية")

        # Run with polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        print(f"❌ خطأ في تشغيل البوت: {e}")
        logger.error(f"Bot startup error: {e}")

if __name__ == '__main__':
    main()
