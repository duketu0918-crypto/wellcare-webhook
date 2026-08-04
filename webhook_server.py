import os, json, hashlib, hmac, base64, logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookParser
from linebot.models import (
    TextSendMessage, TemplateSendMessage,
    ImageCarouselTemplate, ImageCarouselColumn,
    MessageTemplateAction,
    PostbackEvent, MessageEvent
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VERSION = "v1.8.0"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_stores():
    path = os.path.join(DATA_DIR, "stores.json")
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("stores", [])


def load_carousel():
    path = os.path.join(DATA_DIR, "carousel.json")
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def get_store(store_id):
    for s in load_stores():
        if s.get("id") == store_id:
            return s
    return None


def build_image_carousel(cards):
    columns = []
    for card in cards:
        columns.append(
            ImageCarouselColumn(
                image_url=card["imageUrl"],
                action=MessageTemplateAction(
                    label="了解更多",
                    text=card["action_text"]
                )
            )
        )
    return TemplateSendMessage(
        alt_text="本月精選商品",
        template=ImageCarouselTemplate(columns=columns)
    )


def handle_message(event, store):
    user_text = event.message.text.strip()
    cards = load_carousel().get("cards", [])
    logger.info(f"[MSG] store={store.get('id')} text={user_text}")

    for card in cards:
        if user_text == card.get("action_text", ""):
            reply_text = card.get("reply_text", "")
            line_bot_api = LineBotApi(store["channel_access_token"])
            logger.info(f"[REPLY] card={card.get('id')} token_len={len(event.reply_token)}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            return
    # 不符合任何 action_text → 靜默忽略
    logger.info(f"[MSG] no match for: {user_text}")


@app.route("/")
def index():
    return f"Wellcare Webhook {VERSION} OK", 200


@app.route("/webhook/<store_id>", methods=["POST"])
def webhook(store_id):
    store = get_store(store_id)
    if not store:
        logger.warning(f"[STORE] not found: {store_id}")
        abort(404)

    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")
    secret = store.get("channel_secret", "")

    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    if not hmac.compare_digest(expected, signature):
        logger.warning(f"[SIG] invalid for store={store_id}")
        abort(400)

    parser = WebhookParser(store["channel_secret"])
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except Exception as e:
        logger.error(f"[PARSE] {e}")
        abort(400)

    for event in events:
        logger.info(f"[EVENT] type={type(event).__name__} store={store_id}")

        if isinstance(event, PostbackEvent):
            data = event.postback.data
            logger.info(f"[POSTBACK] data={data}")
            if data == "show_carousel":
                carousel_data = load_carousel()
                cards = carousel_data.get("cards", [])
                if not cards:
                    logger.warning("[CAROUSEL] no cards found")
                    continue
                line_bot_api = LineBotApi(store["channel_access_token"])
                msg = build_image_carousel(cards)
                logger.info(f"[CAROUSEL] sending {len(cards)} cards")
                line_bot_api.reply_message(event.reply_token, msg)

        elif isinstance(event, MessageEvent):
            handle_message(event, store)

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))