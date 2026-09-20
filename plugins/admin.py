import os
import sys
import asyncio

from pyrogram import Client, filters

from config import Config
from helper.database import db
from helper.plans import PLANS, get_plan
from helper.admin_access import is_owner


OWNER_FILTER = (
    [int(Config.OWNER_ID)]
    if Config.OWNER_ID
    else [0]
)


def main_bot_only(client):
    return getattr(
        client,
        "is_main_bot",
        False,
    )


# =========================
# OWNER PANEL
# =========================

# =========================
# USER COUNT
# =========================

# =========================
# USER LOOKUP
# =========================

# =========================
# SET PLAN
# =========================

# =========================
# BAN
# =========================

# =========================
# UNBAN
# =========================

# =========================
# BROADCAST
# =========================

# =========================
# RESTART
# =========================
