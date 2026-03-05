from telegram import Update
from telegram.ext import ContextTypes
from config import OWNER_ID
from bot.database import (
    save_user, save_message, get_all_users,
    get_stats, ban_user, unban_user, is_banned,
    save_message_map, get_user_id_by_message
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}!\n\n"
        "Send any message here and admin will get back to you shortly. 💬"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == OWNER_ID:
        text = (
            "🛠 *Admin Commands:*\n"
            "/stats — Bot statistics\n"
            "/broadcast — Reply to a message with this to broadcast\n"
            "/ban `<user_id>` — Ban a user\n"
            "/unban `<user_id>` — Unban a user\n\n"
            "💬 Just *reply* to any forwarded message to respond to that user."
        )
    else:
        text = (
            "ℹ️ *Help:*\n"
            "Just send me a message and we'll reply as soon as possible.\n\n"
            "/start — Welcome message"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


async def _forward_album(context: ContextTypes.DEFAULT_TYPE):
    """Job callback: forwards a buffered media group as a proper album."""
    group_key = context.job.data
    buf = context.bot_data.get("album_buffer", {})
    group = buf.pop(group_key, None)
    if not group:
        return

    forwarded_msgs = await context.bot.forward_messages(
        chat_id=OWNER_ID,
        from_chat_id=group["chat_id"],
        message_ids=sorted(group["message_ids"])
    )

    # Map every forwarded message_id → user_id
    for fwd in forwarded_msgs:
        save_message_map(fwd.message_id, group["user_id"])


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message

    # --- OWNER SIDE: reply to a user ---
    if user.id == OWNER_ID:
        if msg.reply_to_message:
            replied_id = msg.reply_to_message.message_id

            # 1. Check our DB map first — covers ALL users including hidden profiles
            target_user_id = get_user_id_by_message(replied_id)

            # 2. Fallback: read forward_origin (for messages predating the DB map)
            if target_user_id is None:
                origin = getattr(msg.reply_to_message, "forward_origin", None)
                if origin and hasattr(origin, "sender_user") and origin.sender_user:
                    target_user_id = origin.sender_user.id

            if target_user_id is None:
                await msg.reply_text("⚠️ Could not identify the target user.")
                return

            try:
                await context.bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id
                )
                save_message(target_user_id, msg.text or "[media]", direction="outgoing")
            except Exception as e:
                await msg.reply_text(f"❌ Failed to send: {e}")
        return

    # --- USER SIDE: sending a message ---
    save_user(user)

    if is_banned(user.id):
        await msg.reply_text("🚫 You have been banned from using this bot.")
        return

    save_message(user.id, msg.text or "[media]", direction="incoming")

    # --- Album (media group) handling ---
    # Telegram sends each photo/video in an album as a separate message with the
    # same media_group_id. We buffer them for 1 second, then forward all at once
    # so the admin receives them as a proper album.
    if msg.media_group_id:
        buf = context.bot_data.setdefault("album_buffer", {})
        group_key = f"{user.id}:{msg.media_group_id}"

        if group_key not in buf:
            buf[group_key] = {"user_id": user.id, "chat_id": msg.chat_id, "message_ids": []}

        buf[group_key]["message_ids"].append(msg.message_id)

        # Cancel any existing job for this group and reschedule — resets the 1s window
        for job in context.job_queue.get_jobs_by_name(group_key):
            job.schedule_removal()

        context.job_queue.run_once(_forward_album, when=1.0, name=group_key, data=group_key)
        return

    # --- Single message ---
    forwarded = await context.bot.forward_message(
        chat_id=OWNER_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id
    )

    # Map forwarded message_id → user_id so admin can reply to anyone,
    # including users with hidden profiles
    save_message_map(forwarded.message_id, user.id)


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
    await update.message.reply_text(
        f"🚫 User `{context.args[0]}` has been banned.",
        parse_mode="Markdown"
    )


async def unban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    unban_user(int(context.args[0]))
    await update.message.reply_text(
        f"✅ User `{context.args[0]}` has been unbanned.",
        parse_mode="Markdown"
    )
