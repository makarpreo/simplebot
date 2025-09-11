import telebot
import telebot.types as types
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
import config
from main import Car, Note

# Инициализация бота
bot = telebot.TeleBot(config.TOKEN)

# Хранилище сессий пользователей
user_sessions = {}


def get_user_data(user_id):
    """Получает или создает данные пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'current_car_id': 0,
            'chat_id': 0,
            'username': f"user_{user_id}",
            'notes_data': {},
            'editing_note_id': None,
            'editing_note_text': None
        }
    return user_sessions[user_id]


@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
    user_data['username'] = username
    user_data['chat_id'] = message.chat.id

    show_second_menu(message.chat.id, user_id)


def show_second_menu(chat_id, user_id):
    user_data = get_user_data(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)

    btn_set_id = types.InlineKeyboardButton(
        text="🔢 Выбрать машину",
        callback_data="command:/select_car"
    )
    # btn_add_works = types.InlineKeyboardButton(
    #     text="📝 Добавить работы",
    #     callback_data="add_works"
    # )
    # btn_add_parts = types.InlineKeyboardButton(
    #     text="📝 Добавить запчасти",
    #     callback_data="add_parts"
    # )

    markup.add(btn_set_id)
    # markup.add(btn_set_id, btn_add_parts, btn_add_works)
    car = Car()
    car_name = car.get_car_name(user_data['current_car_id']) or f"ID {user_data['current_car_id']}"
    bot.send_message(
        chat_id,
        "🤖 <b>Главное меню</b>\n\n"
        f"<b>ТЕКУЩАЯ МАШИНА: {car_name}</b>\n",
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('command:'))
def handle_command_callback(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    chat_id = call.message.chat.id
    user_data['chat_id'] = chat_id

    command = call.data.split(':')[1]

    class MockMessage:
        def __init__(self, chat_id, text, user_id):
            self.chat = type('Chat', (), {'id': chat_id})()
            self.text = text
            self.from_user = type('User', (), {'id': user_id})()

    mock_message = MockMessage(chat_id, command, user_id)

    if command == '/select_car':
        select_car_from_list(mock_message)
    # elif command == '/add_parts':
    #     ask_parts(mock_message)
    # elif command == '/add_works':
    #     ask_works(mock_message)

    bot.answer_callback_query(call.id, f"Выполняется: {command}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_car:'))
def handle_car_selection(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    chat_id = call.message.chat.id
    user_data['chat_id'] = chat_id

    car_id = int(call.data.split(':')[1])
    user_data['current_car_id'] = car_id

    car = Car()
    car_name = car.get_car_name(car_id) or f"ID {car_id}"

    bot.send_message(chat_id, f"✅ Выбрана машина: {car_name} (ID: {car_id})")
    show_second_menu(chat_id, user_id)
    print_notes_for_car(user_id)

    bot.answer_callback_query(call.id, f"Выбрана машина: {car_name}")


def select_car_from_list(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    car = Car()
    results = car.show_active_list()

    if isinstance(results, str):
        bot.send_message(message.chat.id, results)
        return

    if not results:
        bot.send_message(message.chat.id, "Нет активных машин.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)

    for row in results:
        car_id = row[0]
        car_name = row[1] if len(row) > 1 else f"Машина {car_id}"

        btn_car = types.InlineKeyboardButton(
            text=f"🚗 {car_name} (ID: {car_id})",
            callback_data=f"select_car:{car_id}"
        )
        markup.add(btn_car)

    btn_cancel = types.InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_select"
    )
    markup.add(btn_cancel)

    car = Car()
    car_name = car.get_car_name(user_data['current_car_id']) or f"ID {user_data['current_car_id']}"
    bot.send_message(
        message.chat.id,
        "📋 <b>Выберите машину для работы:</b>\n\n"
        f"Текущая машина: {car_name}",
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_select')
def handle_cancel_selection(call):
    """Обработчик отмены выбора машины"""
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    bot.send_message(user_data['chat_id'], "❌ Выбор машины отменен")
    bot.answer_callback_query(call.id, "Отменено")


@bot.callback_query_handler(func=lambda call: call.data == 'add_works')
def ask_works(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_action:{user_id}")
    )
    bot.send_message(
        user_data['chat_id'],
        "Введите запись которую вы хотите добавить:",
        reply_markup=markup
    )
    bot.register_next_step_handler(call.message, lambda m: add_works_to_car(m, user_id))


def add_works_to_car(message, user_id):
    user_data = get_user_data(user_id)

    note = Note()
    username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
    result = note.add_note(
        note_text=message.text,
        car_id=user_data['current_car_id'],
        user_id=username,
        note_type=1
    )
    bot.send_message(message.chat.id, result)
    print_notes_for_car(user_id)

@bot.callback_query_handler(func=lambda call: call.data == 'add_parts')
def ask_parts(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_action:{user_id}")
    )
    bot.send_message(
        user_data['chat_id'],
        "Введите запись которую вы хотите добавить:",
        reply_markup=markup
    )
    bot.register_next_step_handler(call.message, lambda m: add_parts_to_car(m, user_id))


def add_parts_to_car(message, user_id):
    user_data = get_user_data(user_id)

    note = Note()
    username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
    result = note.add_note(
        note_text=message.text,
        car_id=user_data['current_car_id'],
        user_id=username,
        note_type=0
    )
    bot.send_message(message.chat.id, result)
    print_notes_for_car(user_id)


def print_notes_for_car(user_id):
    user_data = get_user_data(user_id)

    markup = InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        text="Редактировать сообщения",
        callback_data=f"edit_last_note:{user_id}"
    ))
    btn_add_works = types.InlineKeyboardButton(
        text="📝 Добавить работы",
        callback_data="add_works"
    )
    btn_add_parts = types.InlineKeyboardButton(
        text="📝 Добавить запчасти",
        callback_data="add_parts"
    )
    markup.add(btn_add_parts, btn_add_works)
    car = Car()
    note = Note()

    result = note.get_notes_with_ids(user_data['current_car_id'])
    print(result)

    if not result:
        bot.send_message(user_data['chat_id'], 'Для этой машины пока нет записей')
        return None

    if isinstance(result, str) and 'Ошибка' in result:
        bot.send_message(user_data['chat_id'], result)
        return

    user_data['notes_data'] = {}
    for note_id, note_text, username, note_type in result:
        user_data['notes_data'][note_id] = (note_text, username, note_type)

    name = car.get_car_name(user_data['current_car_id']) or f"ID {user_data['current_car_id']}"
    summary = f'🚗 {name}\n\n'

    # Группировка записей по типу и пользователю
    notes_by_type = {0: {}, 1: {}, None: {}}  # 0 = запчасти, 1 = работы

    for note_id, note_text, username, note_type in result:
        if note_type not in notes_by_type:
            notes_by_type[note_type] = {}

        if username not in notes_by_type[note_type]:
            notes_by_type[note_type][username] = []

        notes_by_type[note_type][username].append(note_text)
    if notes_by_type.get(None):
        print(notes_by_type.get(None))
        summary += "🛠️ <b>Старые записи:</b>\n"
        for username, notes in notes_by_type.get(None).items():
            summary += f"  👤 @{username}:\n"
            for i, note_text in enumerate(notes, 1):
                summary += f"    {i}. {note_text}\n"
            summary += "\n"
    # Формирование summary с группировкой
    # Сначала запчасти (type = 0)
    if notes_by_type.get(0):
        summary += "🔧 <b>Запчасти:</b>\n"
        for username, notes in notes_by_type[0].items():
            summary += f"  👤 @{username}:\n"
            for i, note_text in enumerate(notes, 1):
                summary += f"    {i}. {note_text}\n"
            summary += "\n"
        summary += "\n"

    # Затем работы (type = 1)
    if notes_by_type.get(1):
        summary += "🛠️ <b>Работы:</b>\n"
        for username, notes in notes_by_type[1].items():
            summary += f"  👤 @{username}:\n"
            for i, note_text in enumerate(notes, 1):
                summary += f"    {i}. {note_text}\n"
            summary += "\n"


    bot.send_message(user_data['chat_id'], summary, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_last_note:'))
def ask_edit_last_note(call):
    """Показать список сообщений для редактирования"""
    user_id = int(call.data.split(':')[1])
    user_data = get_user_data(user_id)

    note = Note()
    result = note.get_notes_with_ids(user_data['current_car_id'])

    if not result or (isinstance(result, str) and 'Ошибка' in result):
        bot.send_message(user_data['chat_id'], "Нет сообщений для редактирования")
        bot.answer_callback_query(call.id, "Нет сообщений")
        return

    user_data['notes_data'] = {}
    for note_id, note_text, username, note_type in result:
        user_data['notes_data'][note_id] = (note_text, username)

    markup = types.InlineKeyboardMarkup(row_width=1)

    for note_id, note_text, username, note_type in result:
        truncated_text = (note_text[:17] + "...") if len(note_text) > 20 else note_text

        btn_note = types.InlineKeyboardButton(
            text=f"📝 #{note_id}: {truncated_text}",
            callback_data=f"select_note:{note_id}:{user_id}"
        )
        markup.add(btn_note)

    btn_cancel = types.InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"cancel_note_select:{user_id}"
    )
    markup.add(btn_cancel)

    bot.send_message(
        user_data['chat_id'],
        "📋 <b>Выберите сообщение для редактирования:</b>\n\n",
        parse_mode='HTML',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id, "Выберите сообщение")


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_note:'))
def handle_note_selection(call):
    """Обработчик выбора сообщения для редактирования"""
    parts = call.data.split(':')
    note_id = int(parts[1])
    user_id = int(parts[2])
    user_data = get_user_data(user_id)

    if note_id not in user_data.get('notes_data', {}):
        bot.send_message(user_data['chat_id'], "❌ Сообщение не найдено")
        bot.answer_callback_query(call.id, "Ошибка")
        return

    note_text, username = user_data['notes_data'][note_id]

    user_data['editing_note_id'] = note_id
    user_data['editing_note_text'] = note_text

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text="✏️ Редактировать текст", callback_data=f"edit_note_text:{note_id}:{user_id}"),
        types.InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_note:{note_id}:{user_id}")
    )
    markup.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_action:{user_id}"))

    display_text = note_text[:100] + "..." if len(note_text) > 100 else note_text

    bot.send_message(
        user_data['chat_id'],
        f"📝 <b>Сообщение для редактирования:</b>\n\n"
        f"<b>Пользователь:</b> @{username}\n"
        f"<b>Текст:</b>\n<i>{display_text}</i>\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id, f"Выбрано сообщение #{note_id}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_note_text:'))
def start_edit_note_text(call):
    """Начинаем редактирование текста сообщения"""
    parts = call.data.split(':')
    note_id = int(parts[1])
    user_id = int(parts[2])
    user_data = get_user_data(user_id)

    if note_id not in user_data.get('notes_data', {}):
        bot.send_message(user_data['chat_id'], "❌ Сообщение не найдено")
        bot.answer_callback_query(call.id, "Ошибка")
        return

    note_text, username = user_data['notes_data'][note_id]
    user_data['editing_note_id'] = note_id
    user_data['editing_note_text'] = note_text

    display_text = note_text[:100] + "..." if len(note_text) > 100 else note_text
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_action:{user_id}")
    )
    bot.send_message(
        user_data['chat_id'],
        f"✏️Редактирование\n"
        f"<b>Текущий текст:</b>\n<code>{display_text}</code>\n\n"
        f"Введите новый текст сообщения:",
        parse_mode='HTML', reply_markup=markup
    )

    bot.register_next_step_handler(call.message, lambda m: edit_note_text(m, user_id))
    bot.answer_callback_query(call.id, "Введите новый текст")


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_note:'))
def delete_note(call):
    """Удаление сообщения"""
    parts = call.data.split(':')
    note_id = int(parts[1])
    user_id = int(parts[2])
    user_data = get_user_data(user_id)

    if note_id not in user_data.get('notes_data', {}):
        bot.send_message(user_data['chat_id'], "❌ Сообщение не найдено")
        bot.answer_callback_query(call.id, "Ошибка")
        return

    note_text, username = user_data['notes_data'][note_id]

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{note_id}:{user_id}"),
        types.InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_action:{user_id}")
    )

    display_text = note_text[:100] + "..." if len(note_text) > 100 else note_text

    bot.send_message(
        user_data['chat_id'],
        f"🗑️ <b>Подтвердите удаление:</b>\n\n"
        f"<b>ID:</b> {note_id}\n"
        f"<b>Текст:</b>\n<i>{display_text}</i>\n\n"
        f"Вы уверены, что хотите удалить это сообщение?",
        parse_mode='HTML',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id, "Подтвердите удаление")


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete:'))
def confirm_delete_note(call):
    """Подтверждение удаления сообщения"""
    parts = call.data.split(':')
    note_id = int(parts[1])
    user_id = int(parts[2])
    user_data = get_user_data(user_id)

    note = Note()
    result = note.delete_note_by_id(note_id)

    if "успешно" in result.lower() or "удален" in result.lower():
        bot.send_message(user_data['chat_id'], f"✅ Сообщение #{note_id} удалено")
        print_notes_for_car(user_id)
    else:
        bot.send_message(user_data['chat_id'], f"❌ Ошибка при удалении: {result}")

    bot.answer_callback_query(call.id, "Удаление выполнено")


def edit_note_text(message, user_id):
    """Обработчик ввода нового текста для сообщения"""
    user_data = get_user_data(user_id)

    if 'editing_note_id' not in user_data:
        bot.send_message(message.chat.id, "❌ Ошибка: сообщение не выбрано")
        return

    new_text = message.text
    note_id = user_data['editing_note_id']
    old_text = user_data.get('editing_note_text', '')

    note = Note()
    result = note.update_note_text(note_id, new_text)

    if "успешно" in result.lower() or "обновлен" in result.lower():
        old_display = old_text[:100] + "..." if len(old_text) > 100 else old_text
        new_display = new_text[:100] + "..." if len(new_text) > 100 else new_text

        bot.send_message(
            message.chat.id,
            f"✅ Сообщение обновлено:\n\n",
            parse_mode='HTML'
        )
        print_notes_for_car(user_id)
    else:
        bot.send_message(message.chat.id, f"❌ Ошибка при обновлении: {result}")

    user_data.pop('editing_note_id', None)
    user_data.pop('editing_note_text', None)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_action:'))
def handle_cancel_action(call):
    """Обработчик отмены действия"""
    user_id = int(call.data.split(':')[1])
    user_data = get_user_data(user_id)

    bot.send_message(user_data['chat_id'], "❌ Действие отменено")
    bot.answer_callback_query(call.id, "Отменено")

    user_data.pop('editing_note_id', None)
    user_data.pop('editing_note_text', None)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_note_select:'))
def handle_cancel_note_selection(call):
    """Обработчик отмены выбора сообщения"""
    user_id = int(call.data.split(':')[1])
    user_data = get_user_data(user_id)

    bot.send_message(user_data['chat_id'], "❌ Выбор сообщения отменен")
    bot.answer_callback_query(call.id, "Отменено")

    user_data.pop('notes_data', None)


# Остальные функции (init_car_command, add_car, delete_car, show_car_command и т.д.)
# должны быть аналогично адаптированы для использования user_id

# Запуск бота
if __name__ == '__main__':
    print("Бот запущен!")
    bot.infinity_polling()
