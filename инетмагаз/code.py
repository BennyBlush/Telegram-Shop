
import telebot
from telebot import types
from datetime import datetime
import threading
import os
import json

# === НАСТРОЙКИ ===
TOKEN = '8559400099:AAHzhPxeNZKPJngpMK5ESxwUAPZc4As2PAU'
bot = telebot.TeleBot(TOKEN)

# Папки
USER_DATA_DIR = "users_data"
SECURITY_DIR = "security_data"
PROMO_DATA_FILE = os.path.join(SECURITY_DIR, "promocodes.json")
BLOCKED_FILE = os.path.join(SECURITY_DIR, "blocked_log.txt")
BLOCKED_IDS_FILE = os.path.join(SECURITY_DIR, "blocked_ids.txt")
ORDER_COUNTER_FILE = os.path.join(SECURITY_DIR, "order_counter.txt")
PURCHASE_LOGS_FILE = "purchase_logs.txt"

# Создание папок и файлов
for folder in [USER_DATA_DIR, SECURITY_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

for f in [PROMO_DATA_FILE, BLOCKED_IDS_FILE, ORDER_COUNTER_FILE, PURCHASE_LOGS_FILE, "logs.txt", "users.txt"]:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as fw:
            if f.endswith(".json"):
                json.dump({}, fw, indent=4, ensure_ascii=False)
            elif f == ORDER_COUNTER_FILE:
                fw.write("0")
            else:
                fw.write("")

# Данные о товарах
products = {
    "iphone": {"name": "iPhone 15", "price": 80000},
    "macbook": {"name": "MacBook Air", "price": 120000},
    "airpods": {"name": "AirPods Pro", "price": 20000},
    
    "smartwatch_x1": { # Ключ именно такой: "smartwatch_x1"
        "name": "SmartWatch X1", 
        "price": 15000          
    }
}

# --- Вспомогательные функции для работы с файлами и данными ---

def get_next_order_number():
    with open(ORDER_COUNTER_FILE, "r+") as f:
        counter = int(f.read().strip())
        counter += 1
        f.seek(0)
        f.write(str(counter))
        f.truncate()
    return counter

def load_promocodes():
    if not os.path.exists(PROMO_DATA_FILE) or os.stat(PROMO_DATA_FILE).st_size == 0:
        return {}
    with open(PROMO_DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_promocodes(promocodes):
    with open(PROMO_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(promocodes, f, indent=4, ensure_ascii=False)

# --- Функции для работы с данными пользователя ---
def get_user_data_from_file(user_id):
    file_path = os.path.join(USER_DATA_DIR, f"{user_id}.txt")
    data = {
        "registration_date": "Неизвестно",
        "balance": 0,
        "used_promos": [],
        "telegram_username": "Неизвестно",
        "telegram_name": "Неизвестно",
        "telegram_id": str(user_id)
    }
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Дата регистрации:"):
                    data["registration_date"] = line.split(":", 1)[1].strip()
                elif line.startswith("Баланс:"):
                    try: data["balance"] = int(line.split(":", 1)[1].replace("₽", "").strip())
                    except ValueError: pass
                elif line.startswith("Использованные промокоды:"):
                    promos_str = line.split(":", 1)[1].strip()
                    if promos_str: data["used_promos"] = promos_str.split(",")
                elif line.startswith("Телеграм Юзернейм:"):
                    data["telegram_username"] = line.split(":", 1)[1].strip()
                elif line.startswith("Телеграм Имя:"):
                    data["telegram_name"] = line.split(":", 1)[1].strip()
    return data

def update_user_data_to_file(user_id, new_data, user_obj=None):
    file_path = os.path.join(USER_DATA_DIR, f"{user_id}.txt")
    
    existing_data = get_user_data_from_file(user_id)
    existing_data.update(new_data) 

    if user_obj:
        existing_data["telegram_username"] = f"@{user_obj.username}" if user_obj.username else "Нет никнейма"
        existing_data["telegram_name"] = user_obj.first_name
        existing_data["telegram_id"] = str(user_obj.id)

    with open(file_path, "w", encoding="utf-8") as f: 
        f.write(f"Дата регистрации: {existing_data['registration_date']}\n")
        f.write(f"Баланс: {existing_data['balance']}₽\n")
        f.write(f"Использованные промокоды: {','.join(existing_data['used_promos'])}\n")
        f.write(f"Телеграм Юзернейм: {existing_data['telegram_username']}\n")
        f.write(f"Телеграм Имя: {existing_data['telegram_name']}\n")
        f.write(f"Телеграм ID: {existing_data['telegram_id']}\n")
        f.write("-" * 30 + "\n")

# --- Функции логирования ---

def is_blocked(user_id):
    if not os.path.exists(BLOCKED_IDS_FILE):
        return False
    with open(BLOCKED_IDS_FILE, "r") as f:
        blocked_ids = f.read().splitlines()
    return str(user_id) in blocked_ids

def write_general_log(user, action):
    current_time = datetime.now().strftime("%H:%M:%S")
    username = f"@{user.username}" if user.username else "Нет никнейма"
    log_msg = f"[{current_time}] ID: {user.id} | Юзер: {username} | Действие: {action}\n"
    try:
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(log_msg)
    except: pass

def save_to_global_list(user_id):
    user_id = str(user_id)
    if not os.path.exists("users.txt"):
        with open("users.txt", "w") as f: pass
    with open("users.txt", "r") as f:
        users = f.read().splitlines()
    if user_id not in users:
        with open("users.txt", "a") as f:
            f.write(user_id + "\n")

# --- Функция для получения разметки каталога ---
def get_catalog_markup():
    markup = types.InlineKeyboardMarkup()
    for key, p in products.items():
        markup.add(types.InlineKeyboardButton(p['name'], callback_data=f"prod_{key}"))
    return markup

# --- ОБРАБОТЧИКИ БОТА ---

@bot.message_handler(func=lambda message: is_blocked(message.chat.id))
@bot.callback_query_handler(func=lambda call: is_blocked(call.from_user.id))
def handle_blocked_users(update): 
    return 

@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    user_id = user.id
    
    user_data = get_user_data_from_file(user_id)
    if user_data["registration_date"] == "Неизвестно": 
        user_data["registration_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data["balance"] = 0 
        user_data["used_promos"] = []
    
    update_user_data_to_file(user_id, user_data, user_obj=user)
            
    write_general_log(user, "Нажал /start")
    save_to_global_list(user_id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📦 Каталог", "ℹ️ О нас", "📞 Тех.Поддержка", "👤 Профиль")
    
    bot.send_message(message.chat.id, 
                     f"Здравствуйте, {user.first_name}! Выберите функцию:", 
                     reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📦 Каталог")
def catalog(message):
    write_general_log(message.from_user, "Открыл каталог")
    bot.send_message(message.chat.id, "Каталог товаров:", reply_markup=get_catalog_markup()) # Используем новую функцию

@bot.message_handler(func=lambda message: message.text == "ℹ️ О нас")
def about_us(message):
    write_general_log(message.from_user, "Открыл 'О нас'")
    bot.send_message(message.chat.id, "Это тестовый магазин.")

@bot.message_handler(func=lambda message: message.text == "📞 Тех.Поддержка")
def support(message):
    write_general_log(message.from_user, "Открыл Тех.Поддержку")
    bot.send_message(message.chat.id, "Создатель бота - @Benny_NFT, если произошел баг или что-то другое то обращайтесь к нему")

@bot.message_handler(func=lambda message: message.text == "👤 Профиль")
def profile(message):
    user = message.from_user
    user_data = get_user_data_from_file(user.id)
    
    profile_text = (f"📘 Имя: {user_data['telegram_name']}\n"
                    f"💻 ID: {user_data['telegram_id']}\n\n"
                    f"💵 Баланс: {user_data['balance']}₽\n\n"
                    f"📌 Дата регистрации: {user_data['registration_date']}\n")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💵 Пополнить баланс", callback_data="replenish_balance"))
    markup.add(types.InlineKeyboardButton("📘 Активировать промо", callback_data="activate_promo"))
    markup.add(types.InlineKeyboardButton("📦 История заказов", callback_data="order_history"))
    markup.add(types.InlineKeyboardButton("◀️ Вернуться", callback_data="back_to_main_menu"))
    
    bot.send_message(message.chat.id, profile_text, reply_markup=markup)
    write_general_log(user, "Открыл профиль")

# --- Обработчики inline-кнопок из профиля ---

@bot.callback_query_handler(func=lambda call: call.data == "replenish_balance")
def replenish_balance(call):
    bot.answer_callback_query(call.id, "Функция пополнения пока не реализована.")
    bot.send_message(call.message.chat.id, "Здесь будет функция пополнения баланса.")
    write_general_log(call.from_user, "Нажал 'Пополнить баланс'")

@bot.callback_query_handler(func=lambda call: call.data == "activate_promo")
def activate_promo_prompt(call):
    bot.send_message(call.message.chat.id, "Введите промокод:")
    bot.register_next_step_handler(call.message, process_promo_code)
    write_general_log(call.from_user, "Нажал 'Активировать промо'")

def process_promo_code(message):
    user = message.from_user
    promo_code_input = message.text.strip().upper()
    
    promocodes = load_promocodes()
    user_data = get_user_data_from_file(user.id)

    if promo_code_input in promocodes:
        promo_info = promocodes[promo_code_input]
        
        if user.id in promo_info.get("used_by", []):
            bot.send_message(message.chat.id, "Вы уже использовали этот промокод.")
            write_general_log(user, f"Попытка повторного использования промокода: {promo_code_input}")
            profile(message) # Возвращаем в профиль
            return
        
        activation_limit = promo_info.get("limit", -1) 
        current_activations = len(promo_info.get("used_by", []))
        
        if activation_limit != -1 and current_activations >= activation_limit:
            bot.send_message(message.chat.id, "К сожалению, этот промокод больше недоступен.")
            write_general_log(user, f"Промокод '{promo_code_input}' исчерпал лимит активаций.")
            profile(message) # Возвращаем в профиль
            return
        
        bonus_amount = promo_info.get("value", 0)
        user_data["balance"] += bonus_amount
        user_data["used_promos"].append(promo_code_input)
        
        if "used_by" not in promo_info: 
            promo_info["used_by"] = []
        promo_info["used_by"].append(user.id)
        
        promocodes[promo_code_input] = promo_info 
        save_promocodes(promocodes) 

        update_user_data_to_file(user.id, user_data) 
        
        bot.send_message(message.chat.id, 
                         f"Промокод активирован! Ваш баланс пополнен на {bonus_amount}₽. "
                         f"Текущий баланс: {user_data['balance']}₽")
        write_general_log(user, f"Активировал промокод '{promo_code_input}' на {bonus_amount}₽")
    else:
        bot.send_message(message.chat.id, "Неверный промокод.")
        write_general_log(user, f"Ввел неверный промокод: '{promo_code_input}'")
    
    profile(message)

@bot.callback_query_handler(func=lambda call: call.data == "order_history")
def order_history(call):
    bot.answer_callback_query(call.id, "История заказов пока не реализована.")
    bot.send_message(call.message.chat.id, "Здесь будет история ваших заказов.")
    write_general_log(call.from_user, "Нажал 'История заказов'")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main_menu")
def back_to_main_menu_callback(call):
    write_general_log(call.from_user, "Вернулся в главное меню (инлайн)")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📦 Каталог", "ℹ️ О нас", "📞 Тех.Поддержка", "👤 Профиль")
    bot.delete_message(call.message.chat.id, call.message.message_id) 
    bot.send_message(call.message.chat.id, "Вы в главном меню.", reply_markup=markup)

# --- Основные обработчики каталога и покупки ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('prod_'))
def product_view(call):
    p_key = call.data.split('_')[1]
    
    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: 'smartwatch' ---
    if p_key not in products:
        bot.answer_callback_query(call.id, "Товар не найден или устарел. Обновляю каталог...", show_alert=True)
        bot.edit_message_text("Каталог товаров:", call.message.chat.id, call.message.message_id, reply_markup=get_catalog_markup())
        write_general_log(call.from_user, f"Ошибка: Товар '{p_key}' не найден при просмотре (возможно, устаревшая кнопка).")
        return
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    name = products[p_key]['name']
    write_general_log(call.from_user, f"Смотрит товар: {name}")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Купить", callback_data=f"buy_{p_key}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_catalog_inline")) 
    bot.edit_message_text(f"Выбран товар: {name}", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def pay_menu(call):
    user = call.from_user
    product_key = call.data.split('_')[1]
    
    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: 'smartwatch' ---
    if product_key not in products:
        bot.answer_callback_query(call.id, "Товар не найден или устарел. Обновляю каталог...", show_alert=True)
        bot.edit_message_text("Каталог товаров:", call.message.chat.id, call.message.message_id, reply_markup=get_catalog_markup())
        write_general_log(call.from_user, f"Ошибка: Товар '{product_key}' не найден при попытке покупки (возможно, устаревшая кнопка).")
        return
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    product_info = products[product_key]
    user_data = get_user_data_from_file(user.id)
    
    write_general_log(user, f"Перешел к оплате за {product_info['name']}")
    
    pay_url = f"https://t.me/your_payment_bot_name?start=pay_{product_key}_{user.id}" # Замените на реальную ссылку!

    markup = types.InlineKeyboardMarkup()
    
    # Добавляем кнопку оплаты с баланса, если хватает средств
    if user_data["balance"] >= product_info["price"]:
        markup.add(types.InlineKeyboardButton("💳 Оплатить с баланса", callback_data=f"pay_with_balance_{product_key}"))
        
    markup.add(types.InlineKeyboardButton("🔗 Оплатить по ссылке", url=pay_url))
    markup.add(types.InlineKeyboardButton("✅ Проверить платеж", callback_data=f"check_pay_{product_key}"))
    markup.add(types.InlineKeyboardButton("❌ Отменить покупку", callback_data="back_to_catalog_inline"))
    
    bot.edit_message_text("Выберите способ оплаты:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_with_balance_'))
def pay_with_balance(call):
    user = call.from_user
    parts = call.data.split('_')
    product_key = parts[3]
    
    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: 'smartwatch' ---
    if product_key not in products:
        bot.answer_callback_query(call.id, "Товар не найден или устарел. Обновляю каталог...", show_alert=True)
        bot.edit_message_text("Каталог товаров:", call.message.chat.id, call.message.message_id, reply_markup=get_catalog_markup())
        write_general_log(call.from_user, f"Ошибка: Товар '{product_key}' не найден при попытке оплаты с баланса (возможно, устаревшая кнопка).")
        return
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    product_info = products[product_key]
    user_data = get_user_data_from_file(user.id)

    if user_data["balance"] >= product_info["price"]:
        # Списываем баланс
        new_balance = user_data["balance"] - product_info["price"]
        update_user_data_to_file(user.id, {"balance": new_balance}, user_obj=user)
        
        write_general_log(user, f"Оплатил {product_info['name']} ({product_info['price']}₽) с баланса.")
        
        # Логируем покупку и отправляем файл (аналогично check_payment)
        send_purchase_file(call, user, product_info, "Баланс бота")

    else:
        bot.send_message(call.message.chat.id, "Недостаточно средств на балансе.")
        write_general_log(user, f"Попытка оплаты {product_info['name']} с недостаточным балансом.")
        # Возвращаем пользователя к выбору способа оплаты
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Оплатить по ссылке", url=f"https://t.me/your_payment_bot_name?start=pay_{product_key}_{user.id}"))
        markup.add(types.InlineKeyboardButton("✅ Проверить платеж", callback_data=f"check_pay_{product_key}"))
        markup.add(types.InlineKeyboardButton("❌ Отменить покупку", callback_data="back_to_catalog_inline"))
        bot.edit_message_text("Недостаточно средств. Выберите другой способ оплаты:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_pay_"))
def check_payment(call):
    user = call.from_user
    parts = call.data.split('_')
    product_key = parts[2] 

    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: 'smartwatch' ---
    if product_key not in products:
        bot.answer_callback_query(call.id, "Товар не найден или устарел. Обновляю каталог...", show_alert=True)
        bot.edit_message_text("Каталог товаров:", call.message.chat.id, call.message.message_id, reply_markup=get_catalog_markup())
        write_general_log(call.from_user, f"Ошибка: Товар '{product_key}' не найден при проверке оплаты (возможно, устаревшая кнопка).")
        return
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    product_info = products[product_key]
    
    write_general_log(user, f"Нажал 'Проверить платеж' за {product_info['name']}")
    
    # Здесь должна быть логика проверки реальной оплаты через внешнюю систему
    # Для имитации, просто считаем, что оплата прошла, если пользователь не заблокирован
    if not is_blocked(user.id): # Это не совсем правильная логика, тут должна быть проверка платежки
        send_purchase_file(call, user, product_info, "CryptoBot (имитация)")
    else:
        bot.send_message(call.message.chat.id, "Вы заблокированы и не можете совершать покупки.")

# --- Вспомогательная функция для отправки файла и логирования ---
def send_purchase_file(call, user, product_info, payment_method):
    file_name = "textutils"
    if not os.path.exists(file_name): 
        file_name = "textutils.txt"

    if os.path.exists(file_name):
        if os.path.getsize(file_name) == 0:
            bot.send_message(call.message.chat.id, "Ошибка: Файл пуст.")
            return
            
        try:
            order_number = get_next_order_number()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            username_str = f"@{user.username}" if user.username else "Нет никнейма"
            
            purchase_info_text = (
                f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"📃 Товар: {product_info['name']}\n"
                f"💰 Цена: {product_info['price']} ₽ \n"
                f"📦 Кол-во: 1 шт.\n"
                f"💡 Заказ: #{order_number}\n"
                f"🕐 Время заказа: {current_time}\n"
                f"💲 Способ оплаты: {payment_method}\n"
                f"👤 Покупатель ID: {user.id}\n"
                f"👤 Покупатель: {username_str}\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖"
            )

            log_purchase_data = (
                f"[{current_time}] Заказ #{order_number} | Получен файл: {file_name}\n"
                f"ID: {user.id} | Юзер: {username_str} | Ник: {user.first_name}\n"
                f"Товар: {product_info['name']} | Цена: {product_info['price']}₽\n"
                f"Способ оплаты: {payment_method}\n"
                f"-"*30 + "\n"
            )
            with open(PURCHASE_LOGS_FILE, "a", encoding="utf-8") as f:
                f.write(log_purchase_data)

            with open(file_name, "rb") as doc:
                bot.send_document(call.message.chat.id, doc, caption=purchase_info_text)
            
            # Удаляем сообщение с кнопками оплаты
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
            write_general_log(user, f"Получил файл и инфо о покупке за {product_info['name']} (Заказ #{order_number})")
        except Exception as e:
            write_general_log(user, f"Ошибка при отправке/удалении/логировании покупки: {e}")
            bot.send_message(call.message.chat.id, "Ошибка при обработке покупки.")
    else:
        bot.send_message(call.message.chat.id, "Файл не найден.")


@bot.callback_query_handler(func=lambda call: call.data == "back_to_catalog_inline")
def back_to_catalog_inline(call):
    write_general_log(call.from_user, "Вернулся в каталог (инлайн)")
    bot.edit_message_text("Каталог товаров:", call.message.chat.id, call.message.message_id, reply_markup=get_catalog_markup()) # Используем новую функцию

# === АДМИН-ПАНЕЛЬ (КОНСОЛЬ) ===

def admin_console():
    while True:
        print("\n--- АДМИН ПАНЕЛЬ ---")
        print("[1] Рассылка")
        print("[2] Заблокировать пользователя")
        print("[3] Разблокировать пользователя")
        print("[4] Создать промокод") 
        choice = input("Выберите пункт: ")

        if choice == "1":
            text = input("Текст рассылки: ")
            if os.path.exists("users.txt"):
                with open("users.txt", "r") as f:
                    users = f.read().splitlines()
                print(f"Рассылка для {len(users)} чел...")
                for uid in users:
                    try: bot.send_message(uid, text)
                    except: pass
                print("Рассылка завершена.")

        elif choice == "2":
            target_id = input("Введите Telegram ID для БЛОКИРОВКИ: ").strip()
            
            with open(BLOCKED_IDS_FILE, "a") as f:
                f.write(target_id + "\n")
            
            user_data_info = get_user_data_from_file(target_id)
            username_for_log = user_data_info.get("telegram_username", "Неизвестно")
            name_for_log = user_data_info.get("telegram_name", "Неизвестно")

            log_entry = (f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                         f"ЗАБЛОКИРОВАН ID: {target_id} | Юзер: {username_for_log} | Имя: {name_for_log}\n")
            with open(BLOCKED_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
            print(f"Пользователь {target_id} заблокирован.")

        elif choice == "3":
            target_id = input("Введите Telegram ID для РАЗБЛОКИРОВКИ: ").strip()
            if os.path.exists(BLOCKED_IDS_FILE):
                with open(BLOCKED_IDS_FILE, "r") as f:
                    ids = f.read().splitlines()
                if target_id in ids:
                    ids.remove(target_id)
                    with open(BLOCKED_IDS_FILE, "w") as f:
                        f.write("\n".join(ids) + "\n")
                    print(f"Пользователь {target_id} разблокирован.")
                else:
                    print("ID не найден в списке.")
        
        elif choice == "4": # Создание промокода
            promo_code_str = input("Введите слово для промокода: ").strip().upper()
            try:
                promo_value = int(input("Введите сумму (₽), которую получит пользователь: "))
                if promo_value <= 0:
                    print("Сумма должна быть положительной.")
                    continue
            except ValueError:
                print("Неверный формат суммы. Введите число.")
                continue
            
            try:
                limit_input = input("Введите максимальное кол-во активаций (оставьте пустым для безлимита): ").strip()
                if not limit_input:
                    activation_limit = -1 
                else:
                    activation_limit = int(limit_input)
                    if activation_limit <= 0: activation_limit = -1 
            except ValueError:
                activation_limit = -1 
            
            promocodes = load_promocodes()
            if promo_code_str in promocodes:
                print(f"Промокод '{promo_code_str}' уже существует.")
            else:
                promocodes[promo_code_str] = {
                    "value": promo_value, 
                    "limit": activation_limit, 
                    "used_by": [] 
                }
                save_promocodes(promocodes)
                limit_text = f"Лимит активаций: {activation_limit}" if activation_limit != -1 else "Лимит активаций: Безлимит"
                print(f"Промокод '{promo_code_str}' на {promo_value}₽ создан. {limit_text}")

# Запуск админки
threading.Thread(target=admin_console, daemon=True).start()

if __name__ == '__main__':
    print("Бот запущен. Ожидание действий...")
    bot.polling(none_stop=True)
