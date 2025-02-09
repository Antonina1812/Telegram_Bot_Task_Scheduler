import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from pymongo import MongoClient
import datetime

MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_DB = "task_manager"

TELEGRAM_TOKEN = "7553210359:AAEf9IzCvarWhIKMhAJ1Hwy60yhh9nbixGE"

client = MongoClient(MONGO_HOST, MONGO_PORT)
db = client[MONGO_DB]
tasks_collection = db["tasks"]

def add_task(update, context):
    task_text = ' '.join(context.args)
    if not task_text:
        update.message.reply_text("Пожалуйста, введите текст задачи.")
        return

    task = {
        "user_id": update.message.chat_id,
        "text": task_text,
        "created_at": datetime.datetime.now()
    }
    tasks_collection.insert_one(task)
    update.message.reply_text("Задача добавлена!")

def view_tasks(update, context):
    today = datetime.datetime.now().date()
    user_id = update.message.chat_id
    tasks = tasks_collection.find({
        "user_id": user_id,
        "created_at": {
            "$gte": datetime.datetime.combine(today, datetime.time.min),
            "$lt": datetime.datetime.combine(today, datetime.time.max)
        }
    })

    task_list = ""
    for task in tasks:
        task_list += f"- {task['text']}\n"

    if task_list:
        update.message.reply_text(f"Ваши задачи на сегодня:\n{task_list}")
    else:
        update.message.reply_text("Нет задач на сегодня.")

# Функция для удаления задачи (пока просто удаляет все задачи за день)
def delete_tasks(update, context):
    today = datetime.datetime.now().date()
    user_id = update.message.chat_id
    result = tasks_collection.delete_many({
        "user_id": user_id,
        "created_at": {
            "$gte": datetime.datetime.combine(today, datetime.time.min),
            "$lt": datetime.datetime.combine(today, datetime.time.max)
        }
    })
    update.message.reply_text(f"Удалено {result.deleted_count} задач за сегодня.")

def start(update, context):
    update.message.reply_text("Привет! Я твой дневник-бот. Используй /add_task <текст задачи> для добавления задачи, /view_tasks для просмотра задач на сегодня и /delete_tasks для удаления задач за сегодня.")

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add_task", add_task, pass_args=True))
    dp.add_handler(CommandHandler("view_tasks", view_tasks))
    dp.add_handler(CommandHandler("delete_tasks", delete_tasks))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()