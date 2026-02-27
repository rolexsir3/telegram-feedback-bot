from telegram import Update
from telegram.ext import ContextTypes
from config import OWNER_ID
from bot.database import (
    save_user, save_message, get_all_users,
    get_stats, ban_user, unban_user, is_banned
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}!\n\n"
        "Send me any message and the support team will get back to you shortly. "
        "We read every message! 💬"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == OWNER_ID:
        text = (
            "🛠 *Admin Commands:*\n"
            "/stats — Bot statistics\n"
            "/broadcast — Reply to a message with this to broadcast\n"
            "/ban `<user_id>` — Ban a user\n"
            "/unban `<user_id>` — Unban a user\n\n"
            "💬 *Reply* to any forwarded message to respond to that user."
        )
    else:
        text = (
            "ℹ️ *Help:*\n"
            "Just send me a message and we'll reply as soon as possible.\n\n"
            "/start — Welcome message"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message

    if user.id == OWNER_ID:
        if msg.reply_to_message and msg.reply_to_message.forward_origin:
            try:
                origin = msg.reply_to_message.forward_origin
                target_user_id = origin.sender_user.id
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💬 *Reply from Support:*\n{msg.text}",
                    parse_mode="Markdown"
                )
                save_message(target_user_id, msg.text, direction="outgoing")
                await msg.reply_text("✅ Reply sent!")
            except Exception as e:
                await msg.reply_text(f"❌ Could not send reply: {e}")
        return

    save_user(user)

    if is_banned(user.id):
        await msg.reply_text("🚫 You have been banned from using this bot.")
        return

    save_message(user.id, msg.text or "[media]", direction="incoming")

    username_tag = f"@{user.username}" if user.username else "no username"
    caption = (
        f"📩 *New Message*\n"
        f"👤 [{user.first_name}](tg://user?id={user.id}) ({username_tag})\n"
        f"🆔 `{user.id}`\n\n"
        f"💬 {msg.text or '[media/sticker]'}"
    )

    await context.bot.forward_message(
        chat_id=OWNER_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id
    )
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=caption,
        parse_mode="Markdown"
    )

    await msg.reply_text("✅ Your message has been received! We'll reply soon.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    total_users, total_messages = get_stats()
    await update.message.reply_text(
        f"📊 *Bot Statistics:*\n"
        f"👥 Total Users: `{total_users}`\n"
        f"📨 Messages Received: `{total_messages}`",
        parse_mode="Markdown"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    msg = update.message
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ Reply to a message to broadcast it.")
        return

    users = get_all_users()
    success, failed = 0, 0
    for user in users:
        try:
            await context.bot.copy_message(
                chat_id=user["user_id"],
                from_chat_id=msg.chat_id,
                message_id=msg.reply_to_message.message_id
            )
            success += 1
        except Exception:
            failed += 1

    await msg.reply_text(
        f"📢 *Broadcast Complete!*\n✅ Sent: `{success}`\n❌ Failed: `{failed}`",
        parse_mode="Markdown"
    )


async def ban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    ban_user(int(context.args[0]))
    await update.message.reply_text(f"🚫 User `{context.args[0]}` has been banned.", parse_mode="Markdown")


async def unban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    unban_user(int(context.args[0]))
    await update.message.reply_text(f"✅ User `{context.args[0]}` has been unbanned.", parse_mode="Markdown")
