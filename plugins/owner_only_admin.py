
from pyrogram import Client, StopPropagation, filters

from helper.admin_access import is_owner


SENSITIVE_COMMANDS = [
    "admin",
    "owner",
    "users",
    "user",
    "stats",
    "statistics",
    "plans",
    "ownerplans",
    "stars",
    "ownerstars",
    "ownerlimit",
    "bots",
    "botdetails",
    "ownerbots",
    "broadcast",
    "restart",
]


@Client.on_message(
    filters.private & filters.command(SENSITIVE_COMMANDS),
    group=-650,
)
async def owner_only_admin_commands(client, message):
    if not getattr(client, "is_main_bot", False):
        return

    if is_owner(message.from_user.id):
        return

    await message.reply_text(
        "⛔ **Owner only.**\n\n"
        "This management command is restricted to the bot owner."
    )
    raise StopPropagation
