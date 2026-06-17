import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
DATA_FILE = "data.json"

logging.basicConfig(level=logging.INFO)

NAME, DESCRIPTION, REASON = range(3)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👻 Welcome to GhostFileBot!\n\n"
        "Your personal vault for remembering why you said no.\n\n"
        "Commands:\n"
        "/add - Add a new guy to the file\n"
        "/list - See all your entries\n"
        "/lookup - Look up a specific guy\n"
        "/delete - Remove someone from the file"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Let's file him 🗂️\n\nWhat's his name?")
    return NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_name"] = update.message.text.strip()
    await update.message.reply_text("Got it. Short description — who is he? (e.g. 'guy from the gym', 'ex from 2022')")
    return DESCRIPTION

async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_desc"] = update.message.text.strip()
    await update.message.reply_text("And why did you say no?")
    return REASON

async def add_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    name = context.user_data["new_name"]
    desc = context.user_data["new_desc"]
    reason = update.message.text.strip()

    data = load_data()
    if user_id not in data:
        data[user_id] = {}

    data[user_id][name.lower()] = {
        "name": name,
        "description": desc,
        "reason": reason
    }
    save_data(data)

    await update.message.reply_text(f"✅ {name} has been filed. If he ever comes back, you'll know why you said no 👻")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Nothing was saved.")
    return ConversationHandler.END

async def list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = data.get(user_id, {})

    if not entries:
        await update.message.reply_text("Your ghost file is empty. Use /add to file someone 🗂️")
        return

    lines = ["👻 Your Ghost File:\n"]
    for i, (_, entry) in enumerate(entries.items(), 1):
        lines.append(f"{i}. {entry['name']} — {entry['description']}")
    lines.append("\nUse /lookup to read the full file on anyone.")
    await update.message.reply_text("\n".join(lines))

async def lookup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = data.get(user_id, {})

    if not entries:
        await update.message.reply_text("Your ghost file is empty. Use /add to file someone 🗂️")
        return

    keyboard = [
        [InlineKeyboardButton(entry["name"], callback_data=f"lookup:{key}")]
        for key, entry in entries.items()
    ]
    await update.message.reply_text("Who do you want to look up?", reply_markup=InlineKeyboardMarkup(keyboard))

async def lookup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    key = query.data.replace("lookup:", "")
    data = load_data()
    entries = data.get(user_id, {})

    if key not in entries:
        await query.edit_message_text("Couldn't find that entry.")
        return

    entry = entries[key]
    await query.edit_message_text(
        f"🗂️ Ghost File: {entry['name']}\n\n"
        f"📌 Who: {entry['description']}\n\n"
        f"🚩 Why you said no:\n{entry['reason']}"
    )

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = data.get(user_id, {})

    if not entries:
        await update.message.reply_text("Your ghost file is empty.")
        return

    keyboard = [
        [InlineKeyboardButton(f"🗑️ {entry['name']}", callback_data=f"delete:{key}")]
        for key, entry in entries.items()
    ]
    await update.message.reply_text("Who do you want to remove?", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    key = query.data.replace("delete:", "")
    data = load_data()

    if user_id not in data or key not in data[user_id]:
        await query.edit_message_text("Couldn't find that entry.")
        return

    name = data[user_id][key]["name"]
    del data[user_id][key]
    save_data(data)
    await query.edit_message_text(f"✅ {name} has been removed from your ghost file.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reason)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("list", list_entries))
    app.add_handler(CommandHandler("lookup", lookup_start))
    app.add_handler(CommandHandler("delete", delete_start))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(lookup_callback, pattern="^lookup:"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern="^delete:"))

    print("GhostFileBot is running... 👻")
    app.run_polling()

if __name__ == "__main__":
    main()
