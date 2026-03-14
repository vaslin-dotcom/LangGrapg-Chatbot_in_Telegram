import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from graph import app
from schemas import ChatState
import asyncio

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    # Use Telegram chat_id as thread_id — each user gets their own memory
    thread_id = str(update.message.chat_id)

    await update.message.chat.send_action("typing")  # shows "typing..." in Telegram

    initial_state: ChatState = {
        "thread_id": thread_id,
        "latest_input": user_message,
        "latest_response": "",
        "recent_chats": [],
        "relevant_chats": [],
        "exit": False,
        "tool_output": [],
        "tool_query": [],
        "pending_tool_call": []
    }

    config = {"configurable": {"thread_id": thread_id}}

    
    try:
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None, 
            lambda: app.invoke(initial_state, config=config)
        )
        response_text = output.get("latest_response", "Sorry, I couldn't generate a response.")
    except asyncio.TimeoutError:
        response_text = "Sorry, request timed out. Please try again!"
    except Exception as e:
        response_text = f"An error occurred: {str(e)}"

    await update.message.reply_text(response_text)


if __name__ == "__main__":
    print("🤖 Bot is running...")
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.run_polling()
