from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime, time
import pytz
import logging
import os

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
COS_CHAT_ID = os.environ.get("COSCHATID")
OWNER_CHAT_ID = os.environ.get("OWNERCHATID")

# Timezone
SGT = pytz.timezone('Asia/Singapore')

# User data
user_status = {}
user_names = {}
user_teams = {}
name_setting = {}

booking_info = {
    "booking_in": [],
    "booking_out_midday": [],
    "booking_out_lp": []
}

TEAM_OPTIONS = ['Coy HQ', 'Team 1', 'Team 2', 'Team 3', 'Team 4']

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Book In", callback_data='book_in')],
        [InlineKeyboardButton("Book Out", callback_data='book_out')],
        [InlineKeyboardButton("Show In-Camp Personnel", callback_data='show_incamp')],
        [InlineKeyboardButton("Booking In/Booking Out", callback_data='booking')],
        [InlineKeyboardButton("Settings", callback_data='settings')],
    ])

def settings_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Name", callback_data='set_name')],
        [InlineKeyboardButton("Team", callback_data='set_team')],
    ])

def booking_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Booking In, Please State by 1800H", callback_data='booking_in')],
        [InlineKeyboardButton("Booking Out Midday", callback_data='booking_out_midday')],
        [InlineKeyboardButton("Booking Out (LP)", callback_data='booking_out_lp')],
        [InlineKeyboardButton("Remove Name", callback_data='remove_name')]
    ])

async def start(update: Update, context: CallbackContext):
    if update.message.chat.type == 'private':
        user = update.message.from_user
        if user.id in user_names and user.id in user_teams:
            await update.message.reply_text('Hello! What would you like to do?', reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text('Set your Name and Team:', reply_markup=settings_menu_keyboard())

async def settings(update: Update, context: CallbackContext):
    await update.callback_query.message.reply_text('Set your Name and Team:', reply_markup=settings_menu_keyboard())
    await update.callback_query.answer()

async def setname_prompt(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    name_setting[user.id] = True
    await update.callback_query.message.reply_text('Update your name:')
    await update.callback_query.answer()

async def setname(update: Update, context: CallbackContext, user):
    if user.id in name_setting and name_setting[user.id]:
        name = update.message.text
        if name:
            user_names[user.id] = name
            await update.message.reply_text(f'Your name has been set to {name}.')
            if user.id in user_teams:
                await update.message.reply_text('Hello! What would you like to do?', reply_markup=main_menu_keyboard())
            else:
                keyboard = [[InlineKeyboardButton(team, callback_data=team) for team in TEAM_OPTIONS]]
                await update.message.reply_text('Please choose your team:', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text('Please provide a name.')
        name_setting[user.id] = False

async def setteam_prompt(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton(team, callback_data=team) for team in TEAM_OPTIONS]]
    await update.callback_query.message.reply_text('Please choose your team:', reply_markup=InlineKeyboardMarkup(keyboard))
    await update.callback_query.answer()

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user

    if query.data == 'set_name':
        await setname_prompt(update, context)
    elif query.data in TEAM_OPTIONS:
        user_teams[user.id] = query.data
        await query.edit_message_text(text=f'Your team has been set to {query.data}.')
        if user.id in user_names:
            await query.message.reply_text('Hello! What would you like to do?', reply_markup=main_menu_keyboard())
        await query.answer()
    elif query.data == 'set_team':
        await setteam_prompt(update, context)
    elif query.data == 'book_in':
        await bookin(update, context)
    elif query.data == 'book_out':
        await bookout(update, context)
    elif query.data == 'show_incamp':
        await incamp(update, context)
    elif query.data == 'booking':
        await query.message.reply_text('Select an option:', reply_markup=booking_menu_keyboard())
    elif query.data in ['booking_in', 'booking_out_midday', 'booking_out_lp', 'remove_name']:
        await handle_booking(update, context, query.data)
    elif query.data == 'settings':
        await settings(update, context)

async def handle_booking(update: Update, context: CallbackContext, action: str):
    user = update.callback_query.from_user
    name = user_names.get(user.id, user.full_name)
    team = user_teams.get(user.id, 'No team assigned')
    display_name = f"{name} ({team})"

    if action == 'remove_name':
        removed = False
        for key in booking_info.keys():
            if display_name in booking_info[key]:
                booking_info[key].remove(display_name)
                removed = True
        message = "Your name has been removed." if removed else "Your name was not on the list."
    else:
        if display_name in booking_info[action]:
            await update.callback_query.message.reply_text('You already selected this.')
            await update.callback_query.answer()
            return
        booking_info[action].append(display_name)
        message = "Your booking has been updated."

    booking_message = "Booking In, Please State by 1800H:\n" + "\n".join(booking_info["booking_in"]) + \
                      "\n\nBooking Out Midday:\n" + "\n".join(booking_info["booking_out_midday"]) + \
                      "\n\nBooking Out (LP):\n" + "\n".join(booking_info["booking_out_lp"])
    await context.bot.send_message(chat_id=COS_CHAT_ID, text=booking_message)
    await update.callback_query.message.reply_text(message)
    await update.callback_query.answer()

async def bookin(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    if user.id not in user_names or user.id not in user_teams:
        await update.callback_query.message.reply_text('Set your name and team first.')
        return
    if user_status.get(user.id) == 'in':
        await update.callback_query.message.reply_text('You are already booked in.')
        return

    current_time = datetime.now(SGT).strftime('%d/%m/%y %H%MH')
    user_status[user.id] = 'in'
    name = user_names[user.id]
    team = user_teams[user.id]
    message = f'{name} ({team}) booked in at {current_time}.'
    await update.callback_query.message.reply_text('Booked in successfully.')
    await context.bot.send_message(chat_id=COS_CHAT_ID, text=message)

async def bookout(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    if user_status.get(user.id) == 'in':
        user_status[user.id] = 'out'
        current_time = datetime.now(SGT).strftime('%d/%m/%y %H%MH')
        name = user_names[user.id]
        team = user_teams[user.id]
        message = f'{name} ({team}) booked out at {current_time}.'
        await update.callback_query.message.reply_text('Booked out successfully.')
        await context.bot.send_message(chat_id=COS_CHAT_ID, text=message)
    else:
        await update.callback_query.message.reply_text('You are not booked in.')

async def incamp(update: Update, context: CallbackContext):
    in_camp_users = [uid for uid, status in user_status.items() if status == 'in']
    teams = {team: [] for team in TEAM_OPTIONS}
    for uid in in_camp_users:
        name = user_names.get(uid, 'Unknown')
        team = user_teams.get(uid, 'No team assigned')
        teams[team].append(name)

    message = f'Personnel in camp at {datetime.now(SGT).strftime("%d/%m/%y %H%MH")}:\n'
    for team, members in teams.items():
        message += f'\n{team} ({len(members)}):\n' + "\n".join(members) if members else f'\n{team} (0):\n'
    await update.callback_query.message.reply_text(message)

async def private_message_handler(update: Update, context: CallbackContext):
    user = update.message.from_user
    await setname(update, context, user)

async def clear_bookings_daily(context: CallbackContext):
    for key in booking_info:
        booking_info[key].clear()
    await context.bot.send_message(chat_id=COS_CHAT_ID, text="Booking lists cleared.")

async def test_hourly(context: CallbackContext):
    await context.bot.send_message(chat_id=OWNER_CHAT_ID, text="Hourly check-in: bot is alive.")

async def start_msg(context: CallbackContext):
    await context.bot.send_message(chat_id=OWNER_CHAT_ID, text="Bot has started.")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setteam", setteam_prompt))
    application.add_handler(CommandHandler("incamp", incamp))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, private_message_handler))

    job_queue = application.job_queue
    job_queue.run_daily(clear_bookings_daily, time=time(0, 0, 0, tzinfo=SGT))
    job_queue.run_repeating(test_hourly, interval=3600)
    job_queue.run_once(start_msg, 1)

    PORT = int(os.environ.get("PORT", 8443))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()
