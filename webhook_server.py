# -*- coding: utf-8 -*-
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
DATA_DIR  = os.path.join(BASE_DIR, "data")
LOGS_DIR  = os.path.join(BASE_DIR, "logs")
STORES_FILE   = os.path.join(DATA_DIR, "stores.json")
CAROUSEL_FILE = os.path.join(DATA_DIR, "carousel.json")

os.makedirs(LOGS_DIR, exist_ok=True)
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

# ─── 資料載入 ──────────────────────────────────────────
def load_stores():
    with open(STORES_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    # 相容兩種格式：直接陣列 or {"stores": [...]}
    if isinstance(data, list):
        return data
    return data.get("stores", [])

def load_carousel():
    with open(CAROUSEL_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("carousel_cards", data.get("cards", []))

def get_store(store_id):
    # 同時比對 id 和 store_code 欄位，確保相容性
    for s in load_stores():
        if s.get("id") == store_id or s.get("store_code") == store_id:
            return s
    return None

# ─── Flex Carousel 建構 ────────────────────────────────
def build_carousel_flex(cards):
    bubbles = []
    for card in cards:
        if not card.get("enabled", True):
            continue
        # 優先使用新版 actions 陣列，fallback 到舊版欄位
        actions_list = card.get("actions", [])
        if actions_list:
            a = actions_list[0]
            atype = a.get("type", "uri")
            albl  = a.get("label", "了解更多")
            if atype == "uri":
                action = {"type": "uri", "label": albl, "uri": a.get("uri", a.get("url", ""))}
            else:
                action = {"type": "message", "label": albl, "text": a.get("text", "")}
        else:
            atype = card.get("action_type", "uri")
            aval  = card.get("action_value", "")
            albl  = card.get("action_label", "了解更多")
            if atype == "uri":
                action = {"type": "uri", "label": albl, "uri": aval}
            else:
                action = {"type": "message", "label": albl, "text": aval}

        img_url = card.get("thumbnailImageUrl", card.get("thumbnail_image_url", ""))

        bubble = {
            "type": "bubble",
            "size": "mega",
            "hero": {
                "type": "image",
                "url": img_url,
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

# ─── 路由 ──────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    stores = load_stores()
    return jsonify({
        "status": "ok",
        "service": "維康醫療用品 LINE OA Webhook Server",
        "version": "1.1.0",
        "stores_loaded": len(stores),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/health", methods=["GET"])
def health():
    stores = load_stores()
    return jsonify({
        "status": "healthy",
        "stores_count": len(stores)
    })

@app.route("/webhook/<store_id>", methods=["POST"])
def webhook(store_id):
    store = get_store(store_id)
    if not store:
        logger.warning(f"未知門市代碼: {store_id}")
        abort(404)

    token  = store.get("channel_access_token", "").strip()
    secret = store.get("channel_secret", "").strip()
    if not token or not secret:
        logger.error(f"[{store_id}] 缺少 Token 或 Secret")
        abort(500)

    line_bot_api = LineBotApi(token)
    handler      = WebhookHandler(secret)

    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    logger.info(f"[{store_id}] 收到 Webhook body={body[:200]}")

    def send_carousel(reply_token):
        cards = load_carousel()
        flex  = build_carousel_flex(cards)
        if flex:
            line_bot_api.reply_message(
                reply_token,
                FlexSendMessage(alt_text="維康醫療用品 商品目錄", contents=flex)
            )
            logger.info(f"[{store_id}] Carousel 已發送 ({len(flex['contents'])} 張)")
        else:
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="目前無商品資料，請稍後再試。")
            )
            logger.warning(f"[{store_id}] Carousel 無可用卡片")

    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        text = event.message.text.strip()
        logger.info(f"[{store_id}] 文字訊息: {text}")
        keywords = ["商品", "產品", "目錄", "商品目錄", "show_carousel"]
        if any(k in text for k in keywords):
            send_carousel(event.reply_token)
        else:
            logger.info(f"[{store_id}] 非關鍵字訊息，靜默不回應: {text}")

    @handler.add(PostbackEvent)
    def handle_postback(event):
        data = event.postback.data.strip()
        logger.info(f"[{store_id}] Postback data: {data}")
        if data == "show_carousel" or "show_carousel" in data:
            send_carousel(event.reply_token)
        else:
            logger.info(f"[{store_id}] 未處理的 postback: {data}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error(f"[{store_id}] 簽名驗證失敗")
        abort(400)
    except Exception as e:
        logger.error(f"[{store_id}] 處理錯誤: {e}", exc_info=True)
        abort(500)

    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Webhook Server v1.1.0 啟動 port={port}")
    app.run(host="0.0.0.0", port=port, debug=False)
