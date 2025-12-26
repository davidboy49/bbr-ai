import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from collections import deque
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN,
)

chat_logs = {}
app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()


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

    response = client.chat.completions.create(
        model="mistralai/Ministral-8B-Instruct:free",
        messages=[{"role": "user", "content": prompt}],
    )

    summary_text = response.choices[0].message.content
    await update.message.reply_text(summary_text)


application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("summary", summary))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, record))


@app.post("/")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
