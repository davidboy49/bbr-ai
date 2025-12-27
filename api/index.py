import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from openai import APIError, OpenAIError
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from collections import deque
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-bot")

if HF_TOKEN:
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=HF_TOKEN,
    )
else:
    client = None

chat_logs = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if application:
        await application.initialize()
        await application.start()
        if WEBHOOK_URL:
            await application.bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=TELEGRAM_WEBHOOK_SECRET,
            )
            logger.info("Webhook configured for %s", WEBHOOK_URL)

    yield

    if application:
        if WEBHOOK_URL:
            await application.bot.delete_webhook(drop_pending_updates=False)
        await application.stop()
        await application.shutdown()


app = FastAPI(lifespan=lifespan)
application = Application.builder().token(BOT_TOKEN).build() if BOT_TOKEN else None


async def start(update, _):
    message = update.effective_message
    if message:
        await message.reply_text("Bot is live on Vercel 😎")


async def record(update, _):
    message = update.effective_message
    chat_id = update.effective_chat.id if update.effective_chat else None

    if not message or chat_id is None:
        return

    if chat_id not in chat_logs:
        chat_logs[chat_id] = deque(maxlen=200)

    if message.text:
        sender = message.from_user.first_name if message.from_user else "User"
        chat_logs[chat_id].append(f"{sender}: {message.text}")


async def summary(update, _):
    message = update.effective_message
    chat_id = update.effective_chat.id if update.effective_chat else None

    if message is None or chat_id is None:
        return

    if not HF_TOKEN or client is None:
        await message.reply_text("HF_TOKEN is not configured on the server.")
        return

    if chat_id not in chat_logs or len(chat_logs[chat_id]) < 5:
        await message.reply_text("មុិចចឹង pro?????? 😅")
        return

    messages_text = "\n".join(chat_logs[chat_id])

    prompt = f"""
Summarize this Telegram group chat:

Main Topics:
- bullets

Decisions:
- bullets or None

Conflicts:
- bullets or None

Short Summary:
2–3 sentences

Chat:
{messages_text}
"""

    try:
        response = client.chat.completions.create(
            model="mistralai/Ministral-8B-Instruct:free",
            messages=[{"role": "user", "content": prompt}],
        )
    except (APIError, OpenAIError) as exc:
        logger.exception("Model request failed: %s", exc)
        await message.reply_text(
            "Sorry, I couldn't reach the model right now. Please try again."
        )
        return

    summary_text = response.choices[0].message.content
    await message.reply_text(summary_text)


async def on_error(update, context):
    logger.exception("Update handling failed: %s", context.error)


if application:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("summary", summary))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, record))
    application.add_error_handler(on_error)


@app.post("/")
async def webhook(request: Request):
    if not application:
        logger.error("BOT_TOKEN is not configured; webhook ignored.")
        return {"ok": False, "error": "BOT_TOKEN is not configured on the server."}

    if not application.running:
        await application.initialize()
        await application.start()

    if TELEGRAM_WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != TELEGRAM_WEBHOOK_SECRET:
            logger.warning("Webhook secret token mismatch.")
            return {"ok": False, "error": "Invalid secret token"}

    data = await request.json()
    logger.info("Received update: %s", data.get("update_id"))
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

