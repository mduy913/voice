import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import random
import string
import threading
import json
import os
import time
from flask import Flask
BOT_TOKEN = "8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg"
LINK4M_TOKEN = "699ac288bb556c3eae114a58"
RENDER_URL = "https://voice-mleh.onrender.com" 

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

ADMIN_ID = None 
USER_SESSIONS = {} 
OTP_CODES = {}     
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"products": {}, "admin_id": None}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(DB_DATA, f, ensure_ascii=False, indent=4)

DB_DATA = load_db()
if DB_DATA.get("admin_id"):
    ADMIN_ID = DB_DATA["admin_id"]

# --- HÀM XÓA OTP SAU 5 PHÚT ---
def delete_otp_after_delay(otp):
    time.sleep(300)
    if otp in OTP_CODES:
        del OTP_CODES[otp]
        print(f"-> Đã tự động hủy mã OTP: {otp} sau 5 phút.")

# --- WEBHOOK LINK4M ---
@app.route('/callback/<chat_id>/<token>', methods=['GET'])
def link4m_callback(chat_id, token):
    try:
        chat_id = int(chat_id)
        if chat_id in USER_SESSIONS:
            session = USER_SESSIONS[chat_id]
            session["links_done"] += 1
            
            prod_name = session["product"]
            req_links = DB_DATA["products"][prod_name]["links_required"]
            
            if session["links_done"] >= req_links:
                otp = ''.join(random.choices(string.digits, k=6))
                OTP_CODES[otp] = {
                    "chat_id": chat_id, 
                    "product": prod_name,
                    "links_done": session["links_done"]
                }
                del USER_SESSIONS[chat_id]
                
                # Kích hoạt đếm ngược 5 phút
                threading.Thread(target=delete_otp_after_delay, args=(otp,)).start()
                
                msg = (f"🎉 **VƯỢT LINK THÀNH CÔNG!**\n\n"
                       f"Để nhận tài khoản, hãy gõ lệnh:\n"
                       f"`/claim {otp}`\n\n"
                       f"*(Mã này sẽ hết hạn sau 5 phút)*")
                
                bot.send_message(chat_id, msg, parse_mode='Markdown')
            else:
                target_url = f"{RENDER_URL}/callback/{chat_id}/{token}"
                api_url = f"https://link4m.co/api-shorten/v2?api={LINK4M_TOKEN}&url={target_url}"
                res = requests.get(api_url).json()
                if res.get('status') == 'success':
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton(f"👉 VƯỢT LINK {session['links_done'] + 1}/{req_links}", url=res.get('shortenedUrl')))
                    bot.send_message(chat_id, f"Vui lòng vượt thêm {req_links - session['links_done']} link nữa.", reply_markup=markup)
        return "OK", 200
    except Exception as e:
        return "Error", 500

# --- LỆNH CLAIM ---
@bot.message_handler(commands=['claim'])
def claim_acc(message):
    chat_id = message.chat.id
    try:
        otp = message.text.replace('/claim', '').strip()
        if not otp or otp not in OTP_CODES:
            bot.reply_to(message, "❌ Mã OTP không hợp lệ hoặc đã hết hạn (quá 5 phút)!")
            return
            
        session = OTP_CODES[otp]
        if session["chat_id"] != chat_id:
            bot.reply_to(message, "❌ Bạn không phải người sở hữu mã này!")
            return
            
        prod_name = session["product"]
        
        # BÁO LỖI CHUNG NẾU HẾT KHO (Dù vượt bao nhiêu link)
        if prod_name not in DB_DATA["products"] or not DB_DATA["products"][prod_name]["stock"]:
            del OTP_CODES[otp] 
            error_msg = ("❌ Kho đã hết tài khoản!\n"
                         "Vui lòng vượt lại sau khi Admin up thêm acc.\n\n"
                         "Nếu bạn vượt acc trên 5 link, vui lòng liên hệ Admin @mduyk để hỗ trợ.")
            bot.reply_to(message, error_msg)
            return
            
        # NẾU CÒN ACC
        acc = DB_DATA["products"][prod_name]["stock"].pop(0)
        save_db()
        del OTP_CODES[otp]
        
        success_msg = f"🎁 **TÀI KHOẢN CỦA BẠN:**\n\n`{acc['user']} | {acc['pass']}`\n\n*(Hãy copy ngay)*"
        bot.reply_to(message, success_msg, parse_mode='Markdown')
        
    except Exception:
        bot.reply_to(message, "Cú pháp: `/claim 123456`", parse_mode='Markdown')

# --- BOT CƠ BẢN ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global ADMIN_ID
    chat_id = message.chat.id
    if ADMIN_ID is None:
        ADMIN_ID = chat_id
        DB_DATA["admin_id"] = chat_id
        save_db()
        bot.send_message(chat_id, "👑 Bạn là ADMIN đầu tiên!\nDùng /admin để xem quyền.")
        return
    if chat_id == ADMIN_ID:
        bot.send_message(chat_id, "Chào Admin! Dùng /admin để xem quyền.")
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒 CHỌN SẢN PHẨM"))
    bot.send_message(chat_id, "Chào mừng! Bấm nút bên dưới để chọn sản phẩm.", reply_markup=markup)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID: return
    text = "👑 **QUYỀN HẠN**\n1. `/add_prod TênSP | SốLink`\n2. `/add_acc TênSP | user | pass`\n3. `/kho`"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['add_prod'])
def add_prod(message):
    if message.chat.id != ADMIN_ID: return
    try:
        name, links = message.text.replace('/add_prod', '').strip().split('|')
        name, links = name.strip(), links.strip()
        if name not in DB_DATA["products"]:
            DB_DATA["products"][name] = {"links_required": int(links), "stock": []}
            save_db()
            bot.reply_to(message, f"✅ Đã thêm SP: {name} (Cần {links} link)")
        else:
            bot.reply_to(message, "❌ Sản phẩm này đã tồn tại!")
    except: bot.reply_to(message, "VD: `/add_prod VIP | 2`", parse_mode='Markdown')

@bot.message_handler(commands=['add_acc'])
def add_acc(message):
    if message.chat.id != ADMIN_ID: return
    try:
        p, u, pw = message.text.replace('/add_acc', '').strip().split('|')
        p, u, pw = p.strip(), u.strip(), pw.strip()
        if p in DB_DATA["products"]:
            DB_DATA["products"][p]["stock"].append({"user": u, "pass": pw})
            save_db()
            bot.reply_to(message, f"✅ Đã thêm acc vào {p}")
        else: bot.reply_to(message, "❌ Sản phẩm không tồn tại!")
    except: bot.reply_to(message, "VD: `/add_acc VIP | user1 | pass1`", parse_mode='Markdown')

@bot.message_handler(commands=['kho'])
def kho(message):
    if message.chat.id != ADMIN_ID: return
    text = "📦 **TỒN KHO**\n"
    if not DB_DATA["products"]:
        text += "Kho đang trống."
    for name, data in DB_DATA["products"].items():
        text += f"- {name}: {len(data['stock'])} acc (Cần {data['links_required']} link)\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🛒 CHỌN SẢN PHẨM")
def list_products(message):
    markup = InlineKeyboardMarkup()
    for name in DB_DATA["products"]:
        markup.add(InlineKeyboardButton(f"🎁 {name}", callback_data=f"buy_{name}"))
    
    if not DB_DATA["products"]:
        bot.send_message(message.chat.id, "Hiện tại chưa có sản phẩm nào!")
    else:
        bot.send_message(message.chat.id, "Chọn sản phẩm:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_product(call):
    prod_name = call.data.split('_')[1]
    chat_id = call.message.chat.id
    
    if chat_id in USER_SESSIONS:
         bot.answer_callback_query(call.id, "Bạn đang có nhiệm vụ chưa xong!", show_alert=True)
         return
         
    if prod_name not in DB_DATA["products"]:
         bot.answer_callback_query(call.id, "Sản phẩm không tồn tại!", show_alert=True)
         return

    token = f"MDUYK-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    USER_SESSIONS[chat_id] = {"product": prod_name, "links_done": 0}

    req_links = DB_DATA["products"][prod_name]["links_required"]
    target_url = f"{RENDER_URL}/callback/{chat_id}/{token}"
    api_url = f"https://link4m.co/api-shorten/v2?api={LINK4M_TOKEN}&url={target_url}"
    
    try:
        res = requests.get(api_url).json()
        if res.get('status') == 'success':
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"👉 VƯỢT LINK 1/{req_links}", url=res.get('shortenedUrl')))
            bot.send_message(chat_id, f"Đã chọn: {prod_name}\nBấm nút dưới để làm nhiệm vụ.", reply_markup=markup)
    except Exception as e: 
        print("Lỗi tạo link:", e)

def run_bot(): 
    print("Bot đang chạy...")
    bot.polling(none_stop=True, interval=1, timeout=20)

if __name__ == '__main__':
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=3000)
