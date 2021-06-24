import sys
import traceback

import telebot
from telebot import types
from telebot.types import ReplyKeyboardRemove as RemoveMarkup

import settings
import photo_handler
import db_handler

bot = telebot.TeleBot(settings.TG_TOKEN)


@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    if message.text == "/start":
        if settings.START_PHOTO_PATH:
            with open(settings.START_PHOTO_PATH, 'rb') as photo_file:
                photo = photo_file.read()
                bot.send_photo(message.from_user.id, photo, caption=settings.START_MSG,
                               reply_markup=get_start_keyboard())
        else:
            bot.send_message(message.from_user.id, text=settings.START_MSG, reply_markup=get_start_keyboard())
    elif message.text == "/action":
        bot.send_message(message.from_user.id, settings.ACTION_MSG, reply_markup=RemoveMarkup())
        bot.register_next_step_handler(message, action_get_photo)
    elif message.text == "/status":
        bot.send_message(message.from_user.id, "хз", reply_markup=RemoveMarkup())  #
    elif message.text == "/id":
        bot.send_message(message.from_user.id, message.from_user.id, reply_markup=RemoveMarkup())


"""Action branch"""


@bot.message_handler(content_types=['photo', 'document'])
def action_get_photo(message):
    if message.content_type != 'photo' and message.content_type != 'document':
        bot.send_message(message.from_user.id, settings.ACTION_NO_PHOTO_MSG, reply_markup=get_start_keyboard())
        return

    if message.content_type == 'document':
        photo_obj = bot.get_file(message.document.file_id)
    else:
        photo_obj = bot.get_file(message.photo[-1].file_id)

    photo_path = photo_handler.save_photo(photo_obj, bot)
    number = photo_handler.get_number_by_path(photo_path)

    if number:
        bot.send_message(message.from_user.id, settings.ACTION_NUMBER_DEFINED.format(number),
                         reply_markup=get_number_define_keyboard())
        bot.register_next_step_handler(message, action_define_number, number, photo_path)
    else:
        bot.send_message(message.from_user.id, settings.ACTION_NUMBER_UNDEFINED, reply_markup=RemoveMarkup())
        bot.register_next_step_handler(message, action_get_number, photo_path)


def action_define_number(message, number, photo_path):
    if message.text == settings.ACTION_GOOD_NUMBER:
        action_end_get_photo(message, number, photo_path)
    else:
        bot.send_message(message.from_user.id, settings.ACTION_BAD_NUMBER_NEXT, reply_markup=RemoveMarkup())
        bot.register_next_step_handler(message, action_get_number, photo_path)


def action_get_number(message, photo_path):
    try:
        number = int(message.text)
    except Exception:
        number = None
    action_end_get_photo(message, number, photo_path)


def action_end_get_photo(message, number, photo_path):
    if db_handler.validate_number(number):
        if message.from_user.username:
            user_name = "https://t.me/" + message.from_user.username
        else:
            user_name = "hidden"

        db_handler.add_request(message.from_user.id, user_name, photo_path, number)
    else:
        bot.send_message(message.from_user.id, settings.ACTION_USED_RECEIPT, reply_markup=get_start_keyboard())
        return
    user_info = db_handler.get_existing_user_info(message.from_user.id)
    if user_info:
        db_handler.update_request(message.from_user.id, user_name=user_info[0], user_contact=user_info[1])
        action_last(None, message.from_user.id)
    else:
        bot.send_message(message.from_user.id, settings.ACTION_INPUT_NUMBER_MSG, reply_markup=get_contact_keyboard())
        bot.register_next_step_handler(message, action_get_contact)


def action_get_contact(message):
    if message.text:
        contact = message.text
    elif message.contact:
        contact = message.contact.phone_number
    else:
        contact = None

    db_handler.update_request(message.from_user.id, user_contact=contact)

    bot.send_message(message.from_user.id, settings.ACTION_INPUT_NAME_MSG, reply_markup=RemoveMarkup())
    bot.register_next_step_handler(message, action_last)


def action_last(message, user_id=None):
    if message:
        user_id = message.from_user.id
        db_handler.update_request(user_id, user_name=message.text,
                                  request_status=db_handler.REQUEST_NOT_MODERATED_STATUS)
    else:
        db_handler.update_request(user_id, request_status=db_handler.REQUEST_NOT_MODERATED_STATUS)
    bot.send_message(user_id, settings.LAST_ACTION_MSG, reply_markup=get_start_keyboard())
    notify_admins()


"""admin"""


def notify_admins():
    if db_handler.get_not_validated_request()[0]:
        for admin in settings.ADMINS:
            bot.send_message(admin, "Новый запрос ожидает проверки", reply_markup=get_admin_view_keyboard())


@bot.callback_query_handler(func=lambda call: True)
def validate_requests(call):
    request_id, photo_path, receipt_id = db_handler.get_not_validated_request()

    if call.data == "view":
        if request_id:
            if receipt_id:
                msg = f"Номер чека, определенный автоматически:{receipt_id}"
            else:
                msg = "Не удалось определить номер чека автоматически"
            with open(photo_path, 'rb') as photo_file:
                photo = photo_file.read()
            bot.send_photo(call.message.chat.id, photo)
            bot.send_message(call.message.chat.id, msg, reply_markup=get_admin_moderate_keyboard(receipt_id))

        else:
            bot.send_message(call.message.chat.id, "Все запросы было рассмотрены", reply_markup=RemoveMarkup())

    elif call.data == "incorrect receipt_id":
        message = bot.send_message(call.message.chat.id, "Введите номер чека:", reply_markup=RemoveMarkup())
        bot.register_next_step_handler(message, edit_request_receipt_id, request_id)

    elif call.data == "fake receipt":
        db_handler.update_request(None, request_id=request_id, request_status=db_handler.BAD_REQUEST_MODERATED_STATUS)
        bot.send_message(call.message.chat.id, "Запрос отклонен", reply_markup=RemoveMarkup())
        request_validation_end(request_id, call.message.chat.id)

    elif call.data == 'true receipt':
        db_handler.update_request(None, request_id=request_id, request_status=db_handler.REQUEST_MODERATED_STATUS)
        bot.send_message(call.message.chat.id, "Запрос принят", reply_markup=RemoveMarkup())
        request_validation_end(request_id, call.message.chat.id)


def edit_request_receipt_id(message, request_id):
    if db_handler.validate_number(int(message.text)):
        db_handler.update_request(None, request_id=request_id, receipt_id=message.text,
                                  request_status=db_handler.REQUEST_MODERATED_STATUS)
        bot.send_message(message.chat.id, "Запрос обновлен и принят")
    else:
        db_handler.update_request(None, request_id=request_id, receipt_id=message.text,
                                  request_status=db_handler.BAD_REQUEST_MODERATED_STATUS)
        bot.send_message(message.chat.id, "Этот чек уже был использован, запрос был отклонен")
    request_validation_end(request_id, message.chat.id)


def request_validation_end(request_id, chat_id):
    user_id, request_status = db_handler.get_valid_by_request_id(request_id)
    if request_status == db_handler.REQUEST_MODERATED_STATUS:
        bot.send_message(user_id, settings.SUCC_MOD_MSG, reply_markup=get_start_keyboard())
    else:
        bot.send_message(user_id, settings.UNSUCC_MOD_MSG, reply_markup=get_start_keyboard())

    request, _, _ = db_handler.get_not_validated_request()
    if request:
        bot.send_message(chat_id, "Еще остались нерассмотренные запросы", reply_markup=get_admin_view_keyboard())
    else:
        bot.send_message(chat_id, "Все запросы было рассмотрены", reply_markup=RemoveMarkup())


"""Keyboards:"""


def get_start_keyboard():
    keyboard = types.ReplyKeyboardMarkup()
    key_action = types.KeyboardButton('/action')
    keyboard.row(key_action)
    return keyboard


def get_contact_keyboard():
    keyboard = types.ReplyKeyboardMarkup()
    key_contact = types.KeyboardButton(settings.ACTION_CONTACT_BUTTON_TEXT, request_contact=True)
    keyboard.row(key_contact)
    return keyboard


def get_number_define_keyboard():
    keyboard = types.ReplyKeyboardMarkup()
    keyboard.add(types.KeyboardButton(settings.ACTION_GOOD_NUMBER))
    keyboard.add(types.KeyboardButton(settings.ACTION_BAD_NUMBER))
    return keyboard


def get_admin_view_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text='Просмотреть', callback_data='view'))
    return keyboard


def get_admin_moderate_keyboard(receipt_id):
    keyboard = types.InlineKeyboardMarkup()
    if receipt_id:
        keyboard.add(types.InlineKeyboardButton(text='Номер определен неверно', callback_data='incorrect receipt_id'))
        keyboard.add(types.InlineKeyboardButton(text='Чек фейк', callback_data='fake receipt'))
        keyboard.add(types.InlineKeyboardButton(text='Номер определен верно и чек подлинный',
                                                callback_data='true receipt'))
    else:
        keyboard.add(types.InlineKeyboardButton(text='Чек фейк', callback_data='fake receipt'),
                     types.InlineKeyboardButton(text='Чек подлинный', callback_data='incorrect receipt_id'))
    return keyboard


if __name__ == "__main__":
    db_handler.remove_incomplete_requests()
    notify_admins()
    while True:
        try:
            bot.polling(none_stop=True, interval=0)
        except Exception as ex:
            msg, type_, tb = sys.exc_info()
            print(f"Error: {msg}, {type_}")
            traceback.print_tb(tb)
            pass
