import os
import json
import random
from pathlib import Path
from collections import defaultdict

import telebot
from telebot import types

BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise RuntimeError('BOT_TOKEN is not set')
bot = telebot.TeleBot(TOKEN)

def load_questions(filename):
    with (BASE_DIR / filename).open(encoding='utf-8') as f:
        questions = json.load(f)
    assert len(questions) == 519, f'{filename}: expected 519 questions'
    assert len({q['id'] for q in questions}) == len(questions)
    return {q['id']: q for q in questions}

BANKS = {'ru': load_questions('questions.json'), 'en': load_questions('questions_en.json'), 'pl': load_questions('questions_pl.json')}
assert all(set(BANKS['ru']) == set(bank) for bank in BANKS.values()), 'Question IDs differ between languages'
for qid in BANKS['ru']:
    assert all(BANKS['ru'][qid].get('image') == bank[qid].get('image') for bank in BANKS.values()), f'Image mismatch: {qid}'

LANGUAGES = {}
sessions = {}
stats = defaultdict(lambda: {'correct': 0, 'wrong': 0, 'mistakes': set()})

T = {
    'ru': {
        'welcome': '🚛 ADR Test Pro\n\nБазовый курс ADR\n\nВыбери режим подготовки:',
        'choose_language': '🌐 Выбери язык / Choose your language:',
        'training': '📚 Тренировка', 'all': '🎯 Все вопросы', 'mistakes': '❌ Мои ошибки',
        'exam': '📝 Экзамен', 'stats': '📊 Статистика', 'language': '🌐 Язык / Language',
        'next': '➡️ Следующий', 'home': '🏠 Главное меню', 'question': 'Вопрос',
        'choose_mode': 'Сначала выбери режим.', 'empty': 'В этом режиме пока нет вопросов.',
        'finished': '🏁 Тест завершён!', 'right': '✅ Правильно', 'wrong': '❌ Ошибок',
        'result': '📊 Результат', 'exam_mistakes': 'Ошибки экзамена:',
        'correct': '✅ Правильно!', 'incorrect': '❌ Неправильно.',
        'correct_answer': 'Правильный ответ:', 'session_finished': 'Сессия завершена.',
        'total_answers': 'Всего ответов', 'mistakes_count': 'Вопросов в «Мои ошибки»',
    },
    'pl': {
        'welcome': '🚛 ADR Test Pro\n\nKurs podstawowy ADR\n\nWybierz tryb nauki:',
        'choose_language': '🌐 Wybierz język:',
        'training': '📚 Trening', 'all': '🎯 Wszystkie pytania', 'mistakes': '❌ Moje błędy',
        'exam': '📝 Egzamin', 'stats': '📊 Statystyki', 'language': '🌐 Język',
        'next': '➡️ Następne', 'home': '🏠 Menu główne', 'question': 'Pytanie',
        'choose_mode': 'Najpierw wybierz tryb.', 'empty': 'W tym trybie nie ma jeszcze pytań.',
        'finished': '🏁 Test zakończony!', 'right': '✅ Poprawne', 'wrong': '❌ Błędne',
        'result': '📊 Wynik', 'exam_mistakes': 'Błędy na egzaminie:',
        'correct': '✅ Poprawnie!', 'incorrect': '❌ Niepoprawnie.',
        'correct_answer': 'Poprawna odpowiedź:', 'session_finished': 'Sesja zakończona.',
        'total_answers': 'Łącznie odpowiedzi', 'mistakes_count': 'Pytania w „Moich błędach”',
    },
    'en': {
        'welcome': '🚛 ADR Test Pro\n\nADR Basic Course\n\nChoose a practice mode:',
        'choose_language': '🌐 Choose your language / Выбери язык:',
        'training': '📚 Practice', 'all': '🎯 All questions', 'mistakes': '❌ My mistakes',
        'exam': '📝 Exam', 'stats': '📊 Statistics', 'language': '🌐 Language / Язык',
        'next': '➡️ Next', 'home': '🏠 Main menu', 'question': 'Question',
        'choose_mode': 'Please choose a practice mode first.', 'empty': 'No questions in this mode yet.',
        'finished': '🏁 Test completed!', 'right': '✅ Correct', 'wrong': '❌ Incorrect',
        'result': '📊 Score', 'exam_mistakes': 'Exam mistakes:',
        'correct': '✅ Correct!', 'incorrect': '❌ Incorrect.',
        'correct_answer': 'Correct answer:', 'session_finished': 'Session completed.',
        'total_answers': 'Total answers', 'mistakes_count': 'Questions in “My mistakes”',
    },
}

def lang(chat_id):
    return LANGUAGES.get(chat_id, 'ru')

def tr(chat_id, key):
    return T[lang(chat_id)][key]

def language_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton('🇷🇺 Русский', callback_data='lang:ru'),
           types.InlineKeyboardButton('🇬🇧 English', callback_data='lang:en'),
           types.InlineKeyboardButton('🇵🇱 Polski', callback_data='lang:pl'))
    return kb

def main_menu(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton(tr(chat_id, 'training'), callback_data='start_training'),
           types.InlineKeyboardButton(tr(chat_id, 'all'), callback_data='start_all'))
    kb.add(types.InlineKeyboardButton(tr(chat_id, 'mistakes'), callback_data='start_mistakes'),
           types.InlineKeyboardButton(tr(chat_id, 'exam'), callback_data='start_exam'))
    kb.add(types.InlineKeyboardButton(tr(chat_id, 'stats'), callback_data='show_stats'))
    kb.add(types.InlineKeyboardButton(tr(chat_id, 'language'), callback_data='change_language'))
    return kb

def answer_keyboard(qid):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(*[types.InlineKeyboardButton(letter, callback_data=f'ans:{qid}:{letter}') for letter in 'ABC'])
    return kb

def next_keyboard(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(tr(chat_id, 'next'), callback_data='next'))
    kb.add(types.InlineKeyboardButton(tr(chat_id, 'home'), callback_data='home'))
    return kb

def send_question(chat_id):
    s = sessions.get(chat_id)
    if not s:
        bot.send_message(chat_id, tr(chat_id, 'choose_mode'), reply_markup=main_menu(chat_id))
        return
    if s['index'] >= len(s['queue']):
        finish_session(chat_id)
        return
    q = BANKS[s['language']][s['queue'][s['index']]]
    text = (f"🚛 ADR • {tr(chat_id, 'question')} {q.get('number', '')}\n"
            f"📌 {s['index'] + 1}/{len(s['queue'])}\n\n"
            f"{q['question']}\n\n"
            f"A) {q['options']['A']}\n\n"
            f"B) {q['options']['B']}\n\n"
            f"C) {q['options']['C']}")
    image = q.get('image')
    if image:
        img_path = BASE_DIR / image
        if img_path.is_file():
            with img_path.open('rb') as photo:
                bot.send_photo(chat_id, photo)
    bot.send_message(chat_id, text, reply_markup=answer_keyboard(q['id']))

def start_session(chat_id, pool, mode='training', count=None):
    if not pool:
        bot.send_message(chat_id, tr(chat_id, 'empty'), reply_markup=main_menu(chat_id))
        return
    pool = list(pool)
    random.shuffle(pool)
    if count:
        pool = pool[:min(count, len(pool))]
    sessions[chat_id] = {
        'language': lang(chat_id), 'mode': mode,
        'queue': [q['id'] for q in pool], 'index': 0,
        'correct': 0, 'wrong': 0, 'exam_answers': [],
    }
    send_question(chat_id)

def finish_session(chat_id):
    s = sessions.get(chat_id)
    if not s:
        return
    total, correct, wrong = len(s['queue']), s['correct'], s['wrong']
    pct = round(correct / total * 100, 1) if total else 0
    text = (f"{tr(chat_id, 'finished')}\n\n"
            f"{tr(chat_id, 'right')}: {correct}\n"
            f"{tr(chat_id, 'wrong')}: {wrong}\n"
            f"{tr(chat_id, 'result')}: {correct}/{total} ({pct}%)")
    if s['mode'] == 'exam':
        bad = [x for x in s['exam_answers'] if not x['ok']]
        if bad:
            text += '\n\n' + tr(chat_id, 'exam_mistakes')
            for x in bad[:30]:
                text += f"\n• №{x['number']}: {x['selected']} → {x['correct']}"
    sessions.pop(chat_id, None)
    bot.send_message(chat_id, text, reply_markup=main_menu(chat_id))

@bot.message_handler(commands=['start', 'language'])
def cmd_start(message):
    chat_id = message.chat.id
    sessions.pop(chat_id, None)
    bot.send_message(chat_id, tr(chat_id, 'choose_language'), reply_markup=language_menu())

@bot.message_handler(commands=['menu'])
def cmd_menu(message):
    chat_id = message.chat.id
    sessions.pop(chat_id, None)
    bot.send_message(chat_id, tr(chat_id, 'welcome'), reply_markup=main_menu(chat_id))

@bot.message_handler(commands=['test'])
def cmd_test(message):
    chat_id = message.chat.id
    start_session(chat_id, BANKS[lang(chat_id)].values(), count=20)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    bot.answer_callback_query(call.id)
    chat_id, data = call.message.chat.id, call.data
    if data.startswith('lang:'):
        selected_lang = data.split(':', 1)[1]
        if selected_lang not in BANKS:
            return
        LANGUAGES[chat_id] = selected_lang
        sessions.pop(chat_id, None)
        bot.edit_message_text(tr(chat_id, 'welcome'), chat_id=chat_id,
                              message_id=call.message.message_id, reply_markup=main_menu(chat_id))
        return
    if data == 'change_language':
        sessions.pop(chat_id, None)
        bot.edit_message_text(tr(chat_id, 'choose_language'), chat_id=chat_id,
                              message_id=call.message.message_id, reply_markup=language_menu())
        return
    if data == 'home':
        sessions.pop(chat_id, None)
        bot.edit_message_text(tr(chat_id, 'welcome'), chat_id=chat_id,
                              message_id=call.message.message_id, reply_markup=main_menu(chat_id))
        return
    if data in ('start_training', 'start_all', 'start_exam'):
        count = {'start_training': 20, 'start_all': None, 'start_exam': 30}[data]
        mode = 'exam' if data == 'start_exam' else 'training'
        start_session(chat_id, BANKS[lang(chat_id)].values(), mode=mode, count=count)
        return
    if data == 'start_mistakes':
        ids = stats[(chat_id, lang(chat_id))]['mistakes']
        start_session(chat_id, [BANKS[lang(chat_id)][qid] for qid in ids if qid in BANKS[lang(chat_id)]])
        return
    if data == 'show_stats':
        st = stats[(chat_id, lang(chat_id))]
        total = st['correct'] + st['wrong']
        pct = round(st['correct'] / total * 100, 1) if total else 0
        text = (f"{tr(chat_id, 'stats')}\n\n"
                f"{tr(chat_id, 'right')}: {st['correct']}\n"
                f"{tr(chat_id, 'wrong')}: {st['wrong']}\n"
                f"{tr(chat_id, 'total_answers')}: {total}\n"
                f"{tr(chat_id, 'result')}: {pct}%\n"
                f"{tr(chat_id, 'mistakes_count')}: {len(st['mistakes'])}")
        bot.send_message(chat_id, text, reply_markup=main_menu(chat_id))
        return
    if data == 'next':
        if chat_id not in sessions:
            bot.send_message(chat_id, tr(chat_id, 'session_finished'), reply_markup=main_menu(chat_id))
            return
        sessions[chat_id]['index'] += 1
        send_question(chat_id)
        return
    if data.startswith('ans:'):
        try:
            _, qid, selected = data.split(':', 2)
        except ValueError:
            return
        s = sessions.get(chat_id)
        if not s or s['index'] >= len(s['queue']) or qid != s['queue'][s['index']]:
            return
        q = BANKS[s['language']][qid]
        correct = q['correct']
        ok = selected == correct
        st = stats[(chat_id, s['language'])]
        if ok:
            s['correct'] += 1
            st['correct'] += 1
        else:
            s['wrong'] += 1
            st['wrong'] += 1
            st['mistakes'].add(qid)
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
        if s['mode'] == 'exam':
            s['exam_answers'].append({'number': q.get('number', ''), 'selected': selected,
                                      'correct': correct, 'ok': ok})
            s['index'] += 1
            send_question(chat_id)
            return
        result = tr(chat_id, 'correct') if ok else f"{tr(chat_id, 'incorrect')}\n{tr(chat_id, 'correct_answer')} {correct}"
        bot.send_message(chat_id, result, reply_markup=next_keyboard(chat_id))

if __name__ == '__main__':
    print('ADR bot started. Loaded: ' + ', '.join(f'{lang.upper()}={len(bank)}' for lang, bank in BANKS.items()))
    bot.infinity_polling(skip_pending=True)
