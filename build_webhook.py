# -*- coding: utf-8 -*-
import os

BASE = r'C:\LineOA_Control'

code = r'''# -*- coding: utf-8 -*-
from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage
)
import json, os, logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
STORES_FILE  = os.path.join(DATA_DIR, "stores.json")
CAROUSEL_FILE = os.path.join(DATA_DIR, "carousel.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "webhook.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def load_stores():
    with open(STORES_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("stores", [])

def load_carousel():
    with open(CAROUSEL_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("carousel_cards", [])

def get_store(code):
    return next((s for s in load_stores() if s["store_code"] == code), None)

def build_carousel_flex(cards):
    bubbles = []
    for card in cards:
        if not card.get("enabled", True):
            continue
        atype = card.get("action_type", "uri")
        aval  = card.get("action_value", "")
        albl  = card.get("action_label", "了解更多")
        if atype == "uri":
            action = {"type": "uri", "label": albl, "uri": aval}
        else:
            action = {"type": "message", "label": albl, "text": aval}
        bubble = {
            "type": "bubble",
            "size": "mega",
            "hero": {
                "type": "image",
                "url": card.get("thumbnail_image_url", ""),
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "cover",
                "action": action
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "text",
                        "text": card.get("title", ""),
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1A1A2E",
                        "wrap": True
                    },
                    {
                        "type": "text",
                        "text": card.get("text", ""),
                        "size": "sm",
                        "color": "#6B7280",
                        "wrap": True,
                        "margin": "md"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "button",
                        "action": action,
                        "style": "primary",
                        "color": "#06C755",
                        "height": "sm"
                    }
                ]
            }
        }
        bubbles.append(bubble)
    if not bubbles:
        return None
    return {"type": "carousel", "contents": bubbles}

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "ok",
        "service": "維康醫療用品 LINE OA Webhook Server",
        "version": "1.0.0",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})

@app.route("/webhook/<store_code>", methods=["POST"])
def webhook(store_code):
    store = get_store(store_code)
    if not store:
        logger.warning(f"未知門市代碼: {store_code}")
        abort(404)

    token   = store.get("channel_access_token", "").strip()
    secret  = store.get("channel_secret", "").strip()
    if not token or not secret:
        logger.error(f"{store_code} 缺少 Token 或 Secret")
        abort(500)

    line_bot_api = LineBotApi(token)
    handler      = WebhookHandler(secret)

    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    logger.info(f"[{store_code}] 收到 Webhook: {body[:200]}")

    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        text = event.message.text.strip()
        logger.info(f"[{store_code}] 訊息: {text}")
        if text in ["商品", "產品", "目錄", "商品目錄"]:
            send_carousel(line_bot_api, event.reply_token, store_code)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"您好！感謝您聯繫維康醫療用品 {store.get('store_name','')}。\n如需查看商品目錄，請輸入「商品目錄」。")
            )

    @handler.add(PostbackEvent)
    def handle_postback(event):
        data = event.postback.data
        logger.info(f"[{store_code}] Postback: {data}")
        if "action=show_carousel" in data:
            send_carousel(line_bot_api, event.reply_token, store_code)

    def send_carousel(api, reply_token, code):
        cards = load_carousel()
        flex  = build_carousel_flex(cards)
        if flex:
            api.reply_message(
                reply_token,
                FlexSendMessage(alt_text="維康醫療用品 商品目錄", contents=flex)
            )
        else:
            api.reply_message(reply_token, TextSendMessage(text="目前無商品資料"))

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error(f"[{store_code}] 簽名驗證失敗")
        abort(400)
    except Exception as e:
        logger.error(f"[{store_code}] 處理錯誤: {e}")
        abort(500)

    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Webhook Server 啟動 port={port}")
    app.run(host="0.0.0.0", port=port, debug=False)
'''

out = os.path.join(BASE, 'webhook_server.py')
with open(out, 'w', encoding='utf-8') as f:
    f.write(code)
print(f'完成！webhook_server.py 大小: {os.path.getsize(out):,} bytes')
