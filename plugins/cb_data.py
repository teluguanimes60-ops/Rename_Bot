from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply,
)

from config import Config
from helper.database import db
from helper.plans import get_plan
from helper.utils import humanbytes
from plugins.ui import (
    main_menu,
    settings_menu,
    help_menu,
    thumbnail_menu,
    permanent_thumbnail_menu,
    edit_callback_message,
    language_keyboard,
    language_confirm_keyboard,
)



# ============================================================
# LANGUAGE SETTINGS
# ============================================================

@Client.on_callback_query(filters.regex(r"^language_settings$"), group=-3000)
async def cb_language_settings(client: Client, callback_query):
    await callback_query.answer()
    from helper.i18n import t
    user_id = int(callback_query.from_user.id)
    lang = await db.get_language(user_id) or "en"
    await edit_callback_message(
        callback_query,
        f"{t(lang, 'select_title')}\n\n{t(lang, 'select_prompt')}",
        reply_markup=language_keyboard(),
    )


@Client.on_callback_query(filters.regex(r"^lang:select:([a-z]{2,3})$"), group=-3000)
async def cb_language_select(client: Client, callback_query):
    from helper.i18n import is_valid_language, language_label, t
    code = callback_query.matches[0].group(1)
    if not is_valid_language(code):
        await callback_query.answer("Invalid language.", show_alert=True)
        return
    await callback_query.answer()
    await edit_callback_message(
        callback_query,
        f"{t(code, 'select_title')}\n\n"
        f"{language_label(code)}\n\n"
        f"{t(code, 'select_prompt')}",
        reply_markup=language_confirm_keyboard(code),
    )


@Client.on_callback_query(filters.regex(r"^lang:confirm:([a-z]{2,3})$"), group=-3000)
async def cb_language_confirm(client: Client, callback_query):
    from helper.i18n import is_valid_language, language_label, t
    code = callback_query.matches[0].group(1)
    if not is_valid_language(code):
        await callback_query.answer("Invalid language.", show_alert=True)
        return
    user_id = int(callback_query.from_user.id)
    await db.add_user(user_id)
    await db.set_language(user_id, code)
    await callback_query.answer(t(code, "language_saved"), show_alert=True)
    from plugins.start import get_force_sub_status, make_force_sub_text, make_force_sub_keyboard
    joined_count, missing, failed = await get_force_sub_status(client, user_id)
    if missing or failed:
        await edit_callback_message(
            callback_query,
            make_force_sub_text(joined_count, len(missing), len(failed)),
            reply_markup=make_force_sub_keyboard(missing, failed),
        )
        return
    await edit_callback_message(
        callback_query,
        t(code, "language_saved") + "\n\n🔥 **Welcome to AniToon Bot** 🔥",
        reply_markup=main_menu(getattr(client, "is_main_bot", False)),
    )

# ============================================================
# HOME
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^start$")
)
async def cb_start(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    user_id = callback_query.from_user.id
    bot_id = int(getattr(client, "bot_id", 0))

    from helper.i18n import t
    language = await db.get_language(user_id)
    if not language:
        await edit_callback_message(
            callback_query,
            t("en", "select_title") + "\\n\\n" + t("en", "select_prompt"),
            reply_markup=language_keyboard(),
        )
        return

    # --------------------------------------------------------
    # FORCE SUBSCRIBE CHECK
    # --------------------------------------------------------
    try:
        from plugins.start import (
            get_force_sub_status,
            make_force_sub_text,
            make_force_sub_keyboard,
        )

        joined_count, missing, failed = await get_force_sub_status(
            client,
            user_id,
        )

        if missing or failed:
            text = make_force_sub_text(
                joined_count,
                len(missing),
                len(failed),
            )

            markup = make_force_sub_keyboard(
                missing,
                failed,
            )

            try:
                await edit_callback_message(
                    callback_query,
                    text,
                    reply_markup=markup,
                )
            except Exception:
                await callback_query.message.reply_text(
                    text,
                    reply_markup=markup,
                )

            return

    except Exception:
        # Don't destroy the home callback if force-sub
        # verification itself has a temporary problem.
        pass

    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

    try:
        if not await db.is_user_exist(user_id):
            await db.add_user(user_id)
    except Exception:
        pass

    # --------------------------------------------------------
    # PLAN
    # --------------------------------------------------------

    try:
        subscription = await db.get_subscription(
            user_id,
            bot_id,
        )

        plan = get_plan(
            subscription.get(
                "plan",
                "free",
            )
        )

        used = await db.get_usage(
            user_id,
            bot_id,
        )

        remaining = max(
            plan.daily_limit - used,
            0,
        )

        plan_name = plan.name

    except Exception:
        plan_name = "🆓 Free"
        used = 0
        remaining = 10 * 1024 * 1024 * 1024

    # --------------------------------------------------------
    # HOME TEXT
    # --------------------------------------------------------

    text = (
        "🔥 **Welcome to AniToon Bot** 🔥\n\n"
        f"👋 Hello **{callback_query.from_user.first_name}**!\n\n"
        "📂 Send me any file, video or audio "
        "to rename and process it.\n\n"
        f"💎 **Plan:** {plan_name}\n"
        f"🚀 **Used Today:** `{humanbytes(used)}`\n"
        f"⏳ **Remaining:** `{humanbytes(remaining)}`\n\n"
        "✂️ Large files are automatically split "
        "when required."
    )

    keyboard = main_menu(
        getattr(
            client,
            "is_main_bot",
            False,
        )
    )

    try:
        await edit_callback_message(
            callback_query,
            text,
            reply_markup=keyboard,
        )
    except Exception:
        try:
            await client.send_message(
                user_id,
                text,
                reply_markup=keyboard,
            )
        except Exception:
            pass


# ============================================================
# HELP
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^help$")
)
async def cb_help(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    await edit_callback_message(
        callback_query,
        "🛠 **AniToon Help & Usage**\n\n"
        "📂 **Rename:** Send a document, video or audio file "
        "and reply with the new filename.\n\n"
        "🖼 **Thumbnail:** Send an image to save it as your "
        "custom thumbnail.\n\n"
        "📝 **Caption:** Use `/setcaption` or the Settings menu "
        "to save a caption template.\n\n"
        "🏷 **Metadata:** Use `/metadata` to change audio and "
        "subtitle track names.\n\n"
        "💎 **Premium:** Use `/plan` or the Plans button to "
        "view your daily quota and upgrade.\n\n"
        "🤖 **Clone:** The main bot owner can create clone bots "
        "with `/clone`.",
        reply_markup=help_menu(),
    )


# ============================================================
# ABOUT
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^about$")
)
async def cb_about(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    await edit_callback_message(
        callback_query,
        "ℹ️ **About AniToon Promax**\n\n"
        "AniToon Promax Edition is a Telegram file "
        "rename and media-processing bot.\n\n"
        "✅ File renaming\n"
        "✅ Custom captions\n"
        "✅ Custom thumbnails\n"
        "✅ Metadata branding\n"
        "✅ Daily usage limits\n"
        "✅ Telegram Stars Premium plans\n"
        "✅ Clone bot system\n\n"
        "Built for Python 3.11 + Pyrogram 2.0.106 + MongoDB.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="start",
                    )
                ]
            ]
        ),
    )


# ============================================================
# SETTINGS
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^settings$")
)
async def cb_settings(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    from helper.i18n import t
    lang = await db.get_language(callback_query.from_user.id) or "en"
    await edit_callback_message(
        callback_query,
        t(lang, "settings_title") + "\\n\\n" + t(lang, "settings_choose"),
        reply_markup=settings_menu(),
    )


# ============================================================
# CAPTION SETTINGS
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^settings_caption$")
)
async def cb_settings_caption(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    caption = await db.get_caption(
        callback_query.from_user.id
    )

    if caption:
        text = (
            "📝 **Caption Settings**\n\n"
            "Current template:\n"
            f"`{caption}`\n\n"
            "Placeholders:\n"
            "`{filename}`  `{filesize}`  `{duration}`"
        )
    else:
        text = (
            "📝 **Caption Settings**\n\n"
            "No custom caption is currently saved."
        )

    await edit_callback_message(
        callback_query,
        text,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📝 Set / Change",
                        callback_data="set_caption_help",
                    ),
                    InlineKeyboardButton(
                        "🗑 Delete",
                        callback_data="del_caption",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "✏️ Rename Mode",
                        callback_data="rename_settings",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings",
                    )
                ],
            ]
        ),
    )


# ============================================================
# THUMBNAIL SETTINGS
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^settings_thumb$")
)
async def cb_settings_thumb(
    client: Client,
    callback_query,
):
    await callback_query.answer()
    from language.strings import tr
    user_id = int(callback_query.from_user.id)
    lang = await db.get_language(user_id) or "en"
    mode = await db.get_thumbnail_mode(user_id)
    thumb = await db.get_thumbnail(user_id)

    mode_names = {
        "none": "🚫 " + tr(lang, "No Thumbnail"),
        "auto": "🤖 " + tr(lang, "Auto Thumbnail"),
        "custom": "🖼 " + tr(lang, "Custom Thumbnail"),
    }
    saved = "✅ " + tr(lang, "Custom Thumbnail") if thumb else "❌ " + tr(lang, "No Thumbnail")

    text = (
        f"🖼 **{tr(lang, 'Thumbnail')} {tr(lang, 'Settings')}**\n\n"
        f"**{tr(lang, 'Choose an operation:')}**\n"
        f"**Current:** {mode_names.get(mode, mode_names['none'])}\n"
        f"{saved}"
    )
    await edit_callback_message(
        callback_query,
        text,
        reply_markup=thumbnail_menu(),
    )


# ============================================================
# THUMBNAIL MODE
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^thumb_mode:(none|auto|custom)$"),
    group=-2500,
)
async def cb_thumbnail_mode(
    client: Client,
    callback_query,
):
    mode = callback_query.matches[0].group(1)
    user_id = int(callback_query.from_user.id)

    if mode == "custom":
        has_thumbnail = bool(await db.get_thumbnail(user_id))
        await callback_query.answer()

        from language.strings import tr
        lang = await db.get_language(user_id) or "en"
        if not has_thumbnail:
            await edit_callback_message(
                callback_query,
                f"🖼 **{tr(lang, 'Custom Thumbnail')}**\n\n"
                f"➕ {tr(lang, 'Add Thumbnail')}",
                reply_markup=permanent_thumbnail_menu(False),
            )
            return

        await db.set_thumbnail_mode(user_id, "custom")
        await edit_callback_message(
            callback_query,
            f"🖼 **{tr(lang, 'Custom Thumbnail')}**\n\n"
            f"👁 {tr(lang, 'Show Thumbnail')}",
            reply_markup=permanent_thumbnail_menu(True),
        )
        return
    await db.set_thumbnail_mode(user_id, mode)
    await callback_query.answer("Thumbnail mode updated ✅", show_alert=True)
    mode_text = {
        "none": "🚫 No Thumbnail",
        "auto": "🤖 Auto Thumbnail",
    }[mode]
    await edit_callback_message(
        callback_query,
        f"✅ **Thumbnail mode changed**\n\nCurrent mode: **{mode_text}**",
        reply_markup=thumbnail_menu(),
    )
# ============================================================
# VIEW THUMBNAIL
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^view_thumb$")
)
async def cb_view_thumb(
    client: Client,
    callback_query,
):
    await callback_query.answer()
    thumb = await db.get_thumbnail(callback_query.from_user.id)
    if not thumb:
        from language.strings import tr
        lang = await db.get_language(callback_query.from_user.id) or "en"
        return await edit_callback_message(
            callback_query,
            f"❌ **{tr(lang, 'Custom Thumbnail')}**\n\n"
            f"➕ {tr(lang, 'Add Thumbnail')}",
            reply_markup=permanent_thumbnail_menu(False),
        )
    try:
        await client.send_photo(
            callback_query.from_user.id,
            thumb,
            caption="🖼 **Your current custom permanent thumbnail.**",
        )
    except Exception:
        await callback_query.message.reply_text(
            "❌ Unable to display the saved thumbnail."
        )


# ============================================================
# DELETE THUMBNAIL
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^delete_thumb$")
)
async def cb_delete_thumb(
    client: Client,
    callback_query,
):
    await db.set_thumbnail(callback_query.from_user.id, None)
    await db.set_thumbnail_mode(callback_query.from_user.id, "none")
    from language.strings import tr
    lang = await db.get_language(callback_query.from_user.id) or "en"
    await callback_query.answer(
        f"🗑 {tr(lang, 'Delete Custom')} — {tr(lang, 'No Thumbnail')}",
        show_alert=True,
    )
    await edit_callback_message(
        callback_query,
        f"🗑️ **{tr(lang, 'Delete Custom')}**\n\n"
        f"🚫 **{tr(lang, 'No Thumbnail')}**",
        reply_markup=thumbnail_menu(),
    )


# ============================================================
# CREATE CLONE BUTTON
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^create_clone$")
)
async def cb_create_clone(
    client: Client,
    callback_query,
):
    if not getattr(
        client,
        "is_main_bot",
        False,
    ):
        return await callback_query.answer(
            "Clone creation is available only on the main bot.",
            show_alert=True,
        )

    if not Config.IS_CLONE_ALLOWED:
        return await callback_query.answer(
            "Clone Engine is disabled.",
            show_alert=True,
        )

    await callback_query.answer()

    await client.send_message(
        callback_query.from_user.id,
        "🤖 **Create Your AniToon Clone**\n\n"
        "1️⃣ Open @BotFather.\n"
        "2️⃣ Create a new bot.\n"
        "3️⃣ Copy the Bot Token.\n"
        "4️⃣ Reply to this message with the token.\n\n"
        "Your clone will have the normal AniToon features.\n\n"
        "⚠️ Never share your BotFather token publicly.",
        reply_markup=ForceReply(
            selective=True
        ),
    )


# ============================================================
# CAPTION HELP / SET
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^set_caption_help$")
)
async def cb_set_caption_help(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    await client.send_message(
        callback_query.from_user.id,
        "📝 **Enter your caption template.**\n\n"
        "Supported placeholders:\n"
        "`{filename}` — file name\n"
        "`{filesize}` — final file size\n"
        "`{duration}` — video duration\n\n"
        "Example:\n"
        "`🎥 {filename}\\n📦 {filesize}\\n⏱️ {duration}`",
        reply_markup=ForceReply(
            selective=True
        ),
    )


# ============================================================
# METADATA SETTINGS PAGE
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^metadata_settings$")
)
async def cb_metadata_settings(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    user = await db.get_user_data(
        callback_query.from_user.id
    )

    if not user:
        await db.add_user(
            callback_query.from_user.id
        )

        user = await db.get_user_data(
            callback_query.from_user.id
        )

    audio_name = user.get(
        "audio_name",
        "AniToon Official",
    )

    subtitle_name = user.get(
        "sub_name",
        "AniToon Official",
    )

    await edit_callback_message(
        callback_query,
        "🏷️ **AniToon Metadata Branding**\n\n"
        f"🎵 **Audio:** `{audio_name}`\n"
        f"📜 **Subtitle:** `{subtitle_name}`\n\n"
        "Choose an option:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🎵 Set Audio Name",
                        callback_data="set_audio_meta",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📜 Set Subtitle Name",
                        callback_data="set_sub_meta",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Reset",
                        callback_data="reset_metadata",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings",
                    )
                ],
            ]
        ),
    )


# ============================================================
# ============================================================
# FORCE SUBSCRIBE - CHECK & RETRY
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^check_force_sub$")
)
async def cb_check_force_sub(
    client: Client,
    callback_query,
):
    from plugins.start import (
        get_force_sub_status,
        make_force_sub_text,
        make_force_sub_keyboard,
        FORCE_SUB_CHANNELS,
    )

    user_id = callback_query.from_user.id

    (
        joined_count,
        missing_channels,
        failed_channels,
    ) = await get_force_sub_status(
        client,
        user_id,
    )

    total = len(FORCE_SUB_CHANNELS)

    # --------------------------------------------------------
    # ALL JOINED
    # --------------------------------------------------------

    if (
        joined_count == total
        and not missing_channels
        and not failed_channels
    ):
        await callback_query.answer(
            f"✅ Joined {total}/{total} channels!",
            show_alert=True,
        )

        try:
            await edit_callback_message(
                callback_query,
                "✅ **Channel Verification Complete**\n\n"
                f"📊 **Joined:** `{total}/{total}`\n\n"
                "🎉 You can now use AniToon.\n\n"
                "📂 Send me any file, video or audio "
                "to rename and process it.",
                reply_markup=main_menu(
                    getattr(
                        client,
                        "is_main_bot",
                        False,
                    )
                ),
            )
        except Exception:
            await client.send_message(
                user_id,
                "✅ **All required channels joined!**\n\n"
                "📂 Send me a file to get started.",
                reply_markup=main_menu(
                    getattr(
                        client,
                        "is_main_bot",
                        False,
                    )
                ),
            )

        return

    # --------------------------------------------------------
    # STILL MISSING
    # --------------------------------------------------------

    await callback_query.answer(
        f"Joined {joined_count}/{total}",
        show_alert=True,
    )

    text = make_force_sub_text(
        joined_count,
        len(missing_channels),
        len(failed_channels),
    )

    keyboard = make_force_sub_keyboard(
        missing_channels,
        failed_channels,
    )

    try:
        await edit_callback_message(
            callback_query,
            text,
            reply_markup=keyboard,
        )
    except Exception:
        await callback_query.message.reply_text(
            text,
            reply_markup=keyboard,
        )
