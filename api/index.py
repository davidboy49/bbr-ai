import os
from fastapi import FastAPI, Request
from openai import APIError, OpenAIError
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from collections import deque
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")

if HF_TOKEN:
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=HF_TOKEN,
    )
else:
    client = None

chat_logs = {}
app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build() if BOT_TOKEN else None


async def start(update, _):
    await update.message.reply_text("Bot is live on Vercel 😎")


async def record(update, _):
    chat_id = update.message.chat_id

    if chat_id not in chat_logs:
        chat_logs[chat_id] = deque(maxlen=200)

    if update.message.text:
        sender = update.message.from_user.first_name or "User"
        chat_logs[chat_id].append(f"{sender}: {update.message.text}")


async def summary(update, _):
    if not HF_TOKEN or client is None:
        await update.message.reply_text("HF_TOKEN is not configured on the server.")
        return

    chat_id = update.message.chat_id

    if chat_id not in chat_logs or len(chat_logs[chat_id]) < 5:
        await update.message.reply_text("មុិចចឹង pro?????? 😅")
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
        print(f"Model request failed: {exc}")
        await update.message.reply_text(
            "Sorry, I couldn't reach the model right now. Please try again."
        )
        return

    summary_text = response.choices[0].message.content
    await update.message.reply_text(summary_text)


if application:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("summary", summary))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, record))


@app.on_event("startup")
async def on_startup():
    if application:
        await application.initialize()
        await application.start()


@app.on_event("shutdown")
async def on_shutdown():
    if application:
        await application.stop()
        await application.shutdown()


@app.post("/")
async def webhook(request: Request):
    if not application:
        return {"ok": False, "error": "BOT_TOKEN is not configured on the server."}

    if not application.running:
        await application.initialize()
        await application.start()

    if TELEGRAM_WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != TELEGRAM_WEBHOOK_SECRET:
            return {"ok": False, "error": "Invalid secret token"}

    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

