import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import random
import string
import threading
from flask import Flask

# ================= CẤU HÌNH =================
BOT_TOKEN = "8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg"
LINK4M_TOKEN = "699ac288bb556c3eae114a58"
# ĐIỀN ĐÚNG LINK RENDER CỦA BẠN
RENDER_URL = "https://voice-mleh.onrender.com" 
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

ADMIN_ID = None 
PRODUCTS = {}   
USER_SESSIONS = {} 
OTP_CODES = {}     

# --- WEBHOOK LINK4M ---
@app.route('/callback/<chat_id>/<token>', methods=['GET'])
def link4m_callback(chat_id, token):
    try:
        chat_id = int(chat_id)
        print(f"-> Nhận Callback từ ID: {chat_id} | Token: {token}")
        
        if chat_id in USER_SESSIONS:
            session = USER_SESSIONS[chat_id]
            session["links_done"] += 1
            req_links = PRODUCTS[session["product"]]["links_required"]
            
            if session["links_done"] >= req_links:
                otp = ''.join(random.choices(string.digits, k=6))
                OTP_CODES[otp] = {"chat_id": chat_id, "product": session["product"]}
                del USER_SESSIONS[chat_id]
                
                msg = (f"🎉 **VƯỢT LINK THÀNH CÔNG!**\n\n"
                       f"Để nhận tài khoản, hãy gõ lệnh:\n"
                       f"`/claim {otp}`\n\n"
                       f"*(Mã chỉ dùng được 1 lần)*")
                bot.send_message(chat_id, msg, parse_mode='Markdown')
                print(f"-> Đã gửi OTP {otp} cho {chat_id}")
            else:
                target_url = f"{RENDER_URL}/callback/{chat_id}/{token}"
                api_url = f"https://link4m.co/api-shorten/v2?api={LINK4M_TOKEN}&url={target_url}"
                res = requests.get(api_url).json()
                if res.get('status') == 'success':
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton(f"👉 VƯỢT LINK {session['links_done'] + 1}/{req_links}", url=res.get('shortenedUrl')))
                    bot.send_message(chat_id, f"Vui lòng vượt thêm {req_links - session['links_done']} link nữa.", reply_markup=markup)
        else:
            print(f"-> Không tìm thấy phiên của {chat_id}")
        return "OK", 200
    except Exception as e:
        print("LỖI CALLBACK:", e)
        return "Error", 500

# --- LỆNH CLAIM ---
@bot.message_handler(commands=['claim'])
def claim_acc(message):
    chat_id = message.chat.id
    try:
        otp = message.text.replace('/claim', '').strip()
        if not otp or otp not in OTP_CODES:
            bot.reply_to(message, "❌ Mã OTP không hợp lệ hoặc đã hết hạn!")
            return
            
        session = OTP_CODES[otp]
        if session["chat_id"] != chat_id:
            bot.reply_to(message, "❌ Bạn không phải người sở hữu mã này!")
            return
            
        prod_name = session["product"]
        if prod_name not in PRODUCTS or not PRODUCTS[prod_name]["stock"]:
            del OTP_CODES[otp]
            bot.reply_to(message, "❌ Sản phẩm đã hết hàng!")
            return
            
        acc = PRODUCTS[prod_name]["stock"].pop(0)
        del OTP_CODES[otp]
        
        bot.reply_to(message, f"🎁 **TÀI KHOẢN CỦA BẠN:**\n\n`{acc['user']} | {acc['pass']}`\n\n*(Hãy copy ngay)*", parse_mode='Markdown')
        
    except Exception:
        bot.reply_to(message, "Cú pháp: `/claim 123456`", parse_mode='Markdown')

# --- BOT CƠ BẢN ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global ADMIN_ID
    chat_id = message.chat.id
    if ADMIN_ID is None:
        ADMIN_ID = chat_id
        bot.send_message(chat_id, "👑 Bạn là ADMIN!\nDùng /admin để xem quyền.")
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
        PRODUCTS[name.strip()] = {"links_required": int(links.strip()), "stock": []}
        bot.reply_to(message, f"✅ Đã thêm SP: {name.strip()} (Cần {links.strip()} link)")
    except: bot.reply_to(message, "VD: `/add_prod VIP | 2`", parse_mode='Markdown')

@bot.message_handler(commands=['add_acc'])
def add_acc(message):
    if message.chat.id != ADMIN_ID: return
    try:
        p, u, pw = message.text.replace('/add_acc', '').strip().split('|')
        if p.strip() in PRODUCTS:
            PRODUCTS[p.strip()]["stock"].append({"user": u.strip(), "pass": pw.strip()})
            bot.reply_to(message, f"✅ Đã thêm acc vào {p.strip()}")
        else: bot.reply_to(message, "SP không tồn tại!")
    except: bot.reply_to(message, "VD: `/add_acc VIP | user1 | pass1`", parse_mode='Markdown')

@bot.message_handler(commands=['kho'])
def kho(message):
    if message.chat.id != ADMIN_ID: return
    text = "📦 **TỒN KHO**\n"
    for name, data in PRODUCTS.items():
        text += f"- {name}: {len(data['stock'])} acc (Cần {data['links_required']} link)\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🛒 CHỌN SẢN PHẨM")
def list_products(message):
    markup = InlineKeyboardMarkup()
    for name in PRODUCTS:
        markup.add(InlineKeyboardButton(f"🎁 {name}", callback_data=f"buy_{name}"))
    bot.send_message(message.chat.id, "Chọn sản phẩm:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_product(call):
    prod_name = call.data.split('_')[1]
    chat_id = call.message.chat.id
    
    if chat_id in USER_SESSIONS:
         bot.answer_callback_query(call.id, "Bạn đang có nhiệm vụ chưa xong!", show_alert=True)
         return
    if prod_name not in PRODUCTS or not PRODUCTS[prod_name]["stock"]:
         bot.answer_callback_query(call.id, "Sản phẩm đã hết hàng!", show_alert=True)
         return

    token = f"MDUYK-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    USER_SESSIONS[chat_id] = {"product": prod_name, "links_done": 0}

    req_links = PRODUCTS[prod_name]["links_required"]
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
    # Chạy Bot ở luồng riêng để không chặn Flask
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()
    # Chạy Flask
    app.run(host='0.0.0.0', port=3000)
