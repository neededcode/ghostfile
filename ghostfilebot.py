import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

TOKEN = "8911018421:AAE9KebICOGpbR8uYnsksE18b2I5bFo1Nsc"
DATA_FILE = "data.json"

logging.basicConfig(level=logging.INFO)

# Conversation states
NAME, DESCRIPTION, REASON = range(3)
LOOKUP_NAME = 3

# ── Data helpers ──────────────────────────────────────────────────────────────

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_entries(user_id: str, data: dict):
    return data.get(user_id, {})

# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👻 Welcome to *GhostFileBot*\\!\n\n"
        "Your personal vault for remembering *why you said no\\.*\n\n"
        "Commands:\n"
        "/add \\- Add a new guy to the file\n"
        "/list \\- See all your entries\n"
        "/lookup \\- Look up a specific guy\n"
        "/delete \\- Remove someone from the file\n"
        "/help \\- Show this menu again",
        parse_mode="MarkdownV2"
    )

# ── /help ─────────────────────────────────────────────────────────────────────

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ── /add flow ─────────────────────────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Okay, let's file him 🗂️\n\nFirst — what's his *name*?", parse_mode="Markdown")
    return NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_name"] = update.message.text.strip()
    await update.message.reply_text("Got it. Now give a short *description* — who is he? (e.g. 'guy from the gym', 'coworker', 'ex from 2022')", parse_mode="Markdown")
    return DESCRIPTION

async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_desc"] = update.message.text.strip()
    await update.message.reply_text("And the most important part — *why did you say no?*", parse_mode="Markdown")
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

    await update.message.reply_text(
        f"✅ *{name}* has been filed\\.\n\nIf he ever comes back, you'll know exactly why you said no 👻",
        parse_mode="MarkdownV2"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Nothing was saved.")
    return ConversationHandler.END

# ── /list ─────────────────────────────────────────────────────────────────────

async def list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = get_user_entries(user_id, data)

    if not entries:
        await update.message.reply_text("Your ghost file is empty. Use /add to file someone 🗂️")
        return

    lines = ["👻 *Your Ghost File:*\n"]
    for i, (_, entry) in enumerate(entries.items(), 1):
        lines.append(f"{i}\\. *{entry['name']}* — _{entry['description']}_")

    lines.append("\nUse /lookup to read the full file on anyone\\.")
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")

# ── /lookup flow ──────────────────────────────────────────────────────────────

async def lookup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = get_user_entries(user_id, data)

    if not entries:
        await update.message.reply_text("Your ghost file is empty. Use /add to file someone 🗂️")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(entry["name"], callback_data=f"lookup:{key}")]
        for key, entry in entries.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Who do you want to look up?", reply_markup=reply_markup)
    return ConversationHandler.END

async def lookup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    key = query.data.replace("lookup:", "")

    data = load_data()
    entries = get_user_entries(user_id, data)

    if key not in entries:
        await query.edit_message_text("Couldn't find that entry.")
        return

    entry = entries[key]
    await query.edit_message_text(
        f"🗂️ *Ghost File: {entry['name']}*\n\n"
        f"📌 *Who:* {entry['description']}\n\n"
        f"🚩 *Why you said no:*\n_{entry['reason']}_",
        parse_mode="Markdown"
    )

# ── /delete flow ──────────────────────────────────────────────────────────────

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = get_user_entries(user_id, data)

    if not entries:
        await update.message.reply_text("Your ghost file is empty.")
        return

    keyboard = [
        [InlineKeyboardButton(f"🗑️ {entry['name']}", callback_data=f"delete:{key}")]
        for key, entry in entries.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Who do you want to remove from the file?", reply_markup=reply_markup)

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    key = query.data.replace("delete:", "")

    data = load_data()
    entries = get_user_entries(user_id, data)

    if key not in entries:
        await query.edit_message_text("Couldn't find that entry.")
        return

    name = entries[key]["name"]
    del data[user_id][key]
    save_data(data)

    await query.edit_message_text(f"✅ *{name}* has been removed from your ghost file.", parse_mode="Markdown")

# ── Main ──────────────────────────────────────────────────────────────────────

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

    lookup_conv = ConversationHandler(
        entry_points=[CommandHandler("lookup", lookup_start)],
        states={},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("list", list_entries))
    app.add_handler(CommandHandler("delete", delete_start))
    app.add_handler(add_conv)
    app.add_handler(lookup_conv)
    app.add_handler(CallbackQueryHandler(lookup_callback, pattern="^lookup:"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern="^delete:"))

    print("GhostFileBot is running... 👻")
    app.run_polling()

if __name__ == "__main__":
    main()
