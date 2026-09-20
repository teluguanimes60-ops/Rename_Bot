from pyrogram import Client, filters

from config import Config
from helper.database import db
from helper.plans import PLANS, Plan
from helper.utils import humanbytes


def owner_only(user_id: int) -> bool:
    return bool(Config.OWNER_ID and int(user_id) == int(Config.OWNER_ID))

