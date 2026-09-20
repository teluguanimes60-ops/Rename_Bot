"""Public bot command helpers."""

from pyrogram import Client, filters


@Client.on_message(filters.private & filters.command("help"), group=-90)
async def command_help(client, message):
    text = (
        "🛠 **AniToon Help**\n\n"
        "Send a document, video or audio to start processing.\n"
        "Use the buttons in the bot menu to choose your action.\n\n"
        "⚙️ **Available commands**\n"
        "• `/start` — open the main menu\n"
        "• `/help` — show this help\n"
        "• `/cancel` — cancel current processing\n"
        "• `/clone` — create your own clone bot"
    )
    await message.reply_text(text)

