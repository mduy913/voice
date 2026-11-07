import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import random
import string
import threading
import time
from flask import Flask
BOT_TOKEN = "8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg"
LINK4M_TOKEN = "699ac288bb556c3eae114a58"
RENDER_URL = "https://voice-mleh.onrender.com" 
FIREBASE_URL = "https://shopmduy-default-rtdb.asia-southeast1.firebasedatabase.app/"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

ADMIN_ID = None 
USER_SESSIONS = {} 
OTP_CODES = {}     
def get_products():
    try:
        res = requests.get(FIREBASE_URL + "products.json")
        data = res.json()
        return data if data else {}
    except:
        return {}

def save_product(prod_name, links_req):
    requests.put(FIREBASE_URL + f"products/{prod_name}/links_required.json", json=links_req)

def add_acc_to_db(prod_name, user, pwd):
    requests.post(FIREBASE_URL + f"products/{prod_name}/stock.json", json={"user": user, "pass": pwd})

def get_and_remove_acc(prod_name):
    try:
        # Lấy danh sách acc hiện có
        res = requests.get(FIREBASE_URL + f"products/{prod_name}/stock.json")
        stock = res.json()
        if not stock:
            return None
        
        # Lấy acc đầu tiên
        acc_key = list(stock.keys())[0]
        acc_data = stock[acc_key]
        
        # Xóa acc đó khỏi Firebase
        requests.delete(FIREBASE_URL + f"products/{prod_name}/stock/{acc_key}.json")
        return acc_data
    except:
        return None

# --- HÀM XÓA OTP SAU 5 PHÚT ---
def delete_otp_after_delay(otp):
    time.sleep(300)
    if otp in OTP_CODES:
        del OTP_CODES[otp]

# --- WEBHOOK LINK4M ---
@app.route('/callback/<chat_id>/<token>', methods=['GET'])
def link4m_callback(chat_id, token):
    try:
        chat_id = int(chat_id)
        if chat_id in USER_SESSIONS:
            session = USER_SESSIONS[chat_id]
            session["links_done"] += 1
            
            prod_name = session["product"]
            req_links = session["links_required"]
            
            if session["links_done"] >= req_links:
                otp = ''.join(random.choices(string.digits, k=6))
                OTP_CODES[otp] = {
                    "chat_id": chat_id, 
                    "product": prod_name
                }
                del USER_SESSIONS[chat_id]
                
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
        
        # Lấy và xóa acc khỏi Firebase
        acc = get_and_remove_acc(prod_name)
        
        # BÁO LỖI NẾU HẾT KHO
        if not acc:
            del OTP_CODES[otp] 
            error_msg = ("❌ Kho đã hết tài khoản!\n"
                         "Vui lòng vượt lại sau khi Admin up thêm acc.\n\n"
                         "Nếu bạn vượt acc trên 5 link, vui lòng liên hệ Admin @mduyk để hỗ trợ.")
            bot.reply_to(message, error_msg)
            return
            
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
    # Lấy admin id từ firebase
    try:
        res = requests.get(FIREBASE_URL + "admin_id.json")
        saved_admin = res.json()
    except:
        saved_admin = None

    if saved_admin is None:
        requests.put(FIREBASE_URL + "admin_id.json", json=chat_id)
        ADMIN_ID = chat_id
        bot.send_message(chat_id, "👑 Bạn là ADMIN đầu tiên!\nDùng /admin để xem quyền.")
        return
    
    ADMIN_ID = saved_admin
    if chat_id == ADMIN_ID:
        bot.send_message(chat_id, "Chào Admin! Dùng /admin để xem quyền.")
        return
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒 CHỌN SẢN PHẨM"))
    bot.send_message(chat_id, "Chào mừng! Bấm nút bên dưới để chọn sản phẩm.", reply_markup=markup)

@bot.message_handler(commands=['add_prod'])
def add_prod(message):
    if message.chat.id != ADMIN_ID: return
    try:
        name, links = message.text.replace('/add_prod', '').strip().split('|')
        save_product(name.strip(), int(links.strip()))
        bot.reply_to(message, f"✅ Đã thêm SP: {name.strip()} (Cần {links.strip()} link)")
    except: bot.reply_to(message, "VD: `/add_prod VIP | 2`", parse_mode='Markdown')

@bot.message_handler(commands=['add_acc'])
def add_acc(message):
    if message.chat.id != ADMIN_ID: return
    try:
        p, u, pw = message.text.replace('/add_acc', '').strip().split('|')
        add_acc_to_db(p.strip(), u.strip(), pw.strip())
        bot.reply_to(message, f"✅ Đã thêm acc vào {p.strip()}")
    except: bot.reply_to(message, "VD: `/add_acc VIP | user1 | pass1`", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🛒 CHỌN SẢN PHẨM")
def list_products(message):
    products = get_products()
    markup = InlineKeyboardMarkup()
    for name in products:
        markup.add(InlineKeyboardButton(f"🎁 {name}", callback_data=f"buy_{name}"))
    
    if not products:
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
    
    products = get_products()
    if prod_name not in products:
         bot.answer_callback_query(call.id, "Sản phẩm không tồn tại!", show_alert=True)
         return

    token = f"MDUYK-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    req_links = products[prod_name]["links_required"]
    
    USER_SESSIONS[chat_id] = {"product": prod_name, "links_done": 0, "links_required": req_links}

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
    bot.polling(none_stop=True, interval=1, timeout=20)

if __name__ == '__main__':
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=3000)
