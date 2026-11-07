import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import random
import string
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

# ================= CẤU HÌNH =================
BOT_TOKEN = "8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg"
LINK4M_TOKEN = "699ac288bb556c3eae114a58"
WEB_URL = "https://mduy913.github.io/ios-project/" # Sửa lại link web của bạn
RENDER_URL = "https://ten-bot.onrender.com"         # Sẽ điền link Render sau khi tạo xong
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

ADMIN_ID = None 
PRODUCTS = {}   # Lưu sản phẩm: {"VIP": {"links_required": 1, "stock": [{"user":"u1","pass":"p1"}]}}
USER_SESSIONS = {} # Lưu phiên: {chat_id: {"product": "VIP", "links_done": 0}}
OTP_CODES = {}     # Lưu mã OTP: {"849201": {"chat_id": 123, "product": "VIP"}}

# --- API CHO WEB ---
@app.route('/api/claim_otp', methods=['POST'])
def claim_otp():
    data = request.json
    otp = data.get('otp')
    
    if not otp or otp not in OTP_CODES:
        return jsonify({"status": "error", "message": "Mã OTP không hợp lệ hoặc đã hết hạn!"})
    
    session = OTP_CODES[otp]
    prod_name = session["product"]
    
    if prod_name not in PRODUCTS or not PRODUCTS[prod_name]["stock"]:
        del OTP_CODES[otp]
        return jsonify({"status": "error", "message": "Sản phẩm đã hết hàng!"})
        
    acc = PRODUCTS[prod_name]["stock"].pop(0)
    del OTP_CODES[otp] # Xóa mã ngay lập tức
    
    return jsonify({"status": "success", "user": acc["user"], "pass": acc["pass"]})

# --- WEBHOOK LINK4M ---
@app.route('/callback/<chat_id>/<token>', methods=['GET'])
def link4m_callback(chat_id, token):
    try:
        chat_id = int(chat_id)
        if chat_id in USER_SESSIONS:
            session = USER_SESSIONS[chat_id]
            session["links_done"] += 1
            req_links = PRODUCTS[session["product"]]["links_required"]
            
            if session["links_done"] >= req_links:
                otp = ''.join(random.choices(string.digits, k=6))
                OTP_CODES[otp] = {"chat_id": chat_id, "product": session["product"]}
                del USER_SESSIONS[chat_id]
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🌐 TRUY CẬP WEB NHẬN ACC", url=WEB_URL))
                
                msg = (f"🎉 **VƯỢT LINK THÀNH CÔNG!**\n\n"
                       f"Mã OTP của bạn là: `{otp}`\n\n"
                       f"👉 Hãy bấm nút bên dưới để sang Web và nhập mã này.")
                bot.send_message(chat_id, msg, reply_markup=markup, parse_mode='Markdown')
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

# --- BOT TELEGRAM ---
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
    except: pass

def run_bot(): bot.polling(none_stop=True)
if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=3000)
