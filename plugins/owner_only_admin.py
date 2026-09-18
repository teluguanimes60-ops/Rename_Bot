from pyrogram import (
    Client,
    StopPropagation,
    filters,
)

from helper.admin_access import is_owner


SENSITIVE_COMMANDS = [
    "admin",
    "owner",
    "users",
    "user",
    "setplan",
    "ban",
    "unban",
    "broadcast",
    "restart",
]


@Client.on_message(
    filters.private
    & filters.command(
        SENSITIVE_COMMANDS
    ),
    group=-130,
)
async def owner_only_admin_commands(
    client,
    message,
):

    # Only the main bot should expose
    # management commands.
    if not getattr(
        client,
        "is_main_bot",
        False,
    ):
        return

    # Owner can continue normally.
    if is_owner(
        message.from_user.id
    ):
        return

    # Block every non-owner from
    # reaching another management handler.
    await message.reply_text(
        "⛔ **Owner only.**\n\n"
        "This management command is "
        "restricted to the bot owner."
    )

    raise StopPropagation
