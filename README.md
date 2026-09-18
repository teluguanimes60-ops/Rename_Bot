Today 8:35 PM
AniToon_1Bot-main (4) (2).zip
Zip Archive
make the code of fies and push to github repository and make all work perfectly to the environments also and make all work properly GitHub 

Yes. I’ll change the bot so there are no admin accounts at all — only one OWNER_ID has management access.

I can put the deployment settings directly into the code, including:

OWNER_ID = ...
ARCHIVE_CHANNEL_ID = -1004491486679
START_PIC = ""
PORT = 10000
PYROGRAM_WORKERS = 32
MAX_ACTIVE_JOBS = 100
MAX_CONCURRENT_TRANSMISSIONS = 3
MAX_CONCURRENT_PROCESSING = 2
FFMPEG_PRESET = "ultrafast"
FFMPEG_THREADS = 0
PROGRESS_UPDATE_INTERVAL = 1.5
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024

I’ll also remove the ADMIN privilege path so commands such as /users, /ban, /broadcast, /restart, plan controls, owner dashboard, etc. are accessible only to OWNER_ID.

One value I need from you

I need your Telegram numeric user ID for:

OWNER_ID = YOUR_ID

Send me just the number, for example:

123456789

Do not send your bot token, API hash, API ID, or MongoDB URL.

Once you give me the numeric Telegram ID, I can make the GitHub changes with that owner ID rather than guessing it.

i given all rghts to you so add the codes and files in github 
@
GitHub
 

I checked the GitHub connection directly. Your repository access is currently read-only from this ChatGPT GitHub connection, so GitHub is returning:

403 Resource not accessible by integration

That means I cannot truthfully say the files were pushed. The current GitHub app available here supports reading your repository, but this connection is not granting the write operation needed to edit main. OpenAI's current documentation also notes that the standard GitHub app in ChatGPT is read-only for repository code changes; direct code pushes are handled through Codex.

What I have ready to change

I verified your current main branch and prepared the changes for:

Owner only management — no separate admin users.
OWNER_ID is the only management identity.
Existing ADMIN will not grant admin privileges.

Fixed directly in code:

ARCHIVE_CHANNEL_ID = -1004491486679
START_PIC = ""
PORT = 10000
PYROGRAM_WORKERS = 32
MAX_ACTIVE_JOBS = 100
MAX_CONCURRENT_TRANSMISSIONS = 3
MAX_CONCURRENT_PROCESSING = 2
FFMPEG_PRESET = "ultrafast"
FFMPEG_THREADS = 0
PROGRESS_UPDATE_INTERVAL = 1.5
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024
The existing ADMIN environment variable will be treated only as a backward-compatible source for the owner ID, not as an admin list.
All management commands will be owner-only.

I will not invent your Telegram numeric ID.

What you need to do

Use Codex with the GitHub repository connected and give it this instruction:

Update iqleveling/AniToon_1Bot, branch main. Make management strictly owner-only using Config.OWNER_ID; remove all separate admin privileges. Put the requested runtime settings directly in config.py: ARCHIVE_CHANNEL_ID=-1004491486679, START_PIC="", PORT=10000, PYROGRAM_WORKERS=32, MAX_ACTIVE_JOBS=100, MAX_CONCURRENT_TRANSMISSIONS=3, MAX_CONCURRENT_PROCESSING=2, FFMPEG_PRESET="ultrafast", FFMPEG_THREADS=0, PROGRESS_UPDATE_INTERVAL=1.5, and enforce a 2 GiB maximum input file size. Preserve the existing bot functionality and commit the changes to main.

If you reconnect an app that supports write actions, OpenAI's documentation says to reconnect and approve the requested permissions; write workflows require the appropriate GitHub app permissions.

Do not send me your Bot Token, API Hash, MongoDB URI, or other secrets.

give me radme.nmd file to add

Here is the ready-to-add README.md file:

Download README.md

Replace your repository's existing README.md with this one. 

README.md
Document
