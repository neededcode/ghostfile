import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
DATA_FILE = "data.json"

logging.basicConfig(level=logging.INFO)

# Conversation states
NAME, DESCRIPTION, REASON, ICKS, PHOTO = range(5)
ADD_ICK_NAME, ADD_ICK_TEXT = range(5, 7)

# Persistent bottom keyboard
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🗂️ Add a Guy"), KeyboardButton("👀 My List")],
        [KeyboardButton("🔍 Look Up"), KeyboardButton("🤢 Add an Ick")],
        [KeyboardButton("🗑️ Delete"), KeyboardButton("❓ Help")],
    ],
    resize_keyboard=True,
    is_persistent=True
)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👻 Welcome to GhostFileBot!\n\n"
        "Your personal vault for remembering why you said no.\n\n"
        "Use the buttons below to get started 👇",
        reply_markup=MAIN_KEYBOARD
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👻 GhostFileBot Help\n\n"
        "🗂️ Add a Guy — file a new guy\n"
        "👀 My List — see everyone you've filed\n"
        "🔍 Look Up — open a specific guy's file\n"
        "🤢 Add an Ick — add an ick to someone's file\n"
        "🗑️ Delete — remove someone from the file",
        reply_markup=MAIN_KEYBOARD
    )

# ── Add flow ──────────────────────────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Let's file him 🗂️\n\nWhat's his name?")
    return NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_name"] = update.message.text.strip()
    await update.message.reply_text("Short description — who is he? (e.g. 'guy from the gym', 'ex from 2022')")
    return DESCRIPTION

async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_desc"] = update.message.text.strip()
    await update.message.reply_text("Why did you say no?")
    return REASON

async def add_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_reason"] = update.message.text.strip()
    context.user_data["new_icks"] = []
    await update.message.reply_text(
        "Any icks? Send them one by one, then tap Done when finished.\n"
        "Or tap Skip to skip.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("✅ Done"), KeyboardButton("⏭️ Skip")]],
            resize_keyboard=True
        )
    )
    return ICKS

async def add_ick_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "✅ Done":
        return await add_icks_done(update, context)
    if text == "⏭️ Skip":
        return await skip_icks(update, context)
    context.user_data["new_icks"].append(text)
    await update.message.reply_text(
        f"Added! 🤢 Send another ick or tap Done.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("✅ Done"), KeyboardButton("⏭️ Skip")]],
            resize_keyboard=True
        )
    )
    return ICKS

async def add_icks_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Got it! Now send a photo or screenshot for his file.\nOr tap Skip.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("⏭️ Skip")]],
            resize_keyboard=True
        )
    )
    return PHOTO

async def skip_icks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_icks"] = []
    await update.message.reply_text(
        "Now send a photo or screenshot for his file.\nOr tap Skip.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("⏭️ Skip")]],
            resize_keyboard=True
        )
    )
    return PHOTO

async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data["new_photo"] = photo.file_id
    await _save_entry(update, context)
    return ConversationHandler.END

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_photo"] = None
    await _save_entry(update, context)
    return ConversationHandler.END

async def _save_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    name = context.user_data["new_name"]
    data = load_data()
    if user_id not in data:
        data[user_id] = {}

    data[user_id][name.lower()] = {
        "name": name,
        "description": context.user_data["new_desc"],
        "reason": context.user_data["new_reason"],
        "icks": context.user_data.get("new_icks", []),
        "photo": context.user_data.get("new_photo"),
        "date": datetime.now().strftime("%B %d, %Y")
    }
    save_data(data)
    await update.message.reply_text(
        f"✅ {name} has been filed. If he ever comes back, you'll know exactly why you said no 👻",
        reply_markup=MAIN_KEYBOARD
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Nothing was saved.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

# ── List ──────────────────────────────────────────────────────────────────────

async def list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = data.get(user_id, {})

    if not entries:
        await update.message.reply_text("Your ghost file is empty. Tap 🗂️ Add a Guy to file someone!", reply_markup=MAIN_KEYBOARD)
        return

    lines = ["👻 Your Ghost File:\n"]
    for i, (_, entry) in enumerate(entries.items(), 1):
        date = entry.get("date", "unknown date")
        lines.append(f"{i}. {entry['name']} — {entry['description']} (filed {date})")
    lines.append("\nTap 🔍 Look Up to read the full file on anyone.")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_KEYBOARD)

# ── Lookup ────────────────────────────────────────────────────────────────────

async def lookup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = data.get(user_id, {})

    if not entries:
        await update.message.reply_text("Your ghost file is empty. Tap 🗂️ Add a Guy to file someone!", reply_markup=MAIN_KEYBOARD)
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
    icks = entry.get("icks", [])
    ick_text = "\n\n🤢 Icks:\n" + "\n".join(f"  — {ick}" for ick in icks) if icks else ""
    date = entry.get("date", "unknown date")

    text = (
        f"🗂️ Ghost File: {entry['name']}\n\n"
        f"📌 Who: {entry['description']}\n"
        f"📅 Filed: {date}\n\n"
        f"🚩 Why you said no:\n{entry['reason']}"
        f"{ick_text}"
    )

    photo = entry.get("photo")
    if photo:
        await query.message.reply_photo(photo=photo, caption=text)
        await query.edit_message_text("Here's his file 👇")
    else:
        await query.edit_message_text(text)

# ── Add Ick flow ──────────────────────────────────────────────────────────────

async def addick_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = data.get(user_id, {})

    if not entries:
        await update.message.reply_text("Your ghost file is empty. Add someone first!", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(entry["name"], callback_data=f"addick:{key}")]
        for key, entry in entries.items()
    ]
    await update.message.reply_text("Who are you adding an ick for?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_ICK_NAME

async def addick_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("addick:", "")
    context.user_data["ick_target"] = key
    await query.edit_message_text("What's the ick? 🤢")
    return ADD_ICK_TEXT

async def addick_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    key = context.user_data["ick_target"]
    ick = update.message.text.strip()

    data = load_data()
    if user_id in data and key in data[user_id]:
        if "icks" not in data[user_id][key]:
            data[user_id][key]["icks"] = []
        data[user_id][key]["icks"].append(ick)
        save_data(data)
        name = data[user_id][key]["name"]
        await update.message.reply_text(f"🤢 Ick added to {name}'s file!", reply_markup=MAIN_KEYBOARD)
    else:
        await update.message.reply_text("Couldn't find that entry.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

# ── Delete ────────────────────────────────────────────────────────────────────

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    entries = data.get(user_id, {})

    if not entries:
        await update.message.reply_text("Your ghost file is empty.", reply_markup=MAIN_KEYBOARD)
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

# ── Message router (handles button taps) ─────────────────────────────────────

async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🗂️ Add a Guy":
        return await add_start(update, context)
    elif text == "👀 My List":
        await list_entries(update, context)
    elif text == "🔍 Look Up":
        await lookup_start(update, context)
    elif text == "🤢 Add an Ick":
        return await addick_start(update, context)
    elif text == "🗑️ Delete":
        await delete_start(update, context)
    elif text == "❓ Help":
        await help_cmd(update, context)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start),
            MessageHandler(filters.Regex("^🗂️ Add a Guy$"), add_start),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reason)],
            ICKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ick_item)],
            PHOTO: [
                MessageHandler(filters.PHOTO, add_photo),
                MessageHandler(filters.Regex("^⏭️ Skip$"), skip_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    addick_conv = ConversationHandler(
        entry_points=[
            CommandHandler("addick", addick_start),
            MessageHandler(filters.Regex("^🤢 Add an Ick$"), addick_start),
        ],
        states={
            ADD_ICK_NAME: [CallbackQueryHandler(addick_name_callback, pattern="^addick:")],
            ADD_ICK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, addick_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("list", list_entries))
    app.add_handler(CommandHandler("lookup", lookup_start))
    app.add_handler(CommandHandler("delete", delete_start))
    app.add_handler(add_conv)
    app.add_handler(addick_conv)
    app.add_handler(CallbackQueryHandler(lookup_callback, pattern="^lookup:"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern="^delete:"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex("^(👀 My List|🔍 Look Up|🗑️ Delete|❓ Help)$"),
        button_router
    ))

    print("GhostFileBot is running... 👻")
    app.run_polling()

if __name__ == "__main__":
    main()
