from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pymongo import MongoClient
import datetime
import redis
from celery import Celery
import tasks as t
import constants as c
from bson.objectid import ObjectId

redis_client = redis.Redis(host=c.REDIS_HOST, port=c.REDIS_PORT)
celery = Celery('tasks', broker=c.CELERY_BROKER_URL, backend=c.CELERY_RESULT_BACKEND)
celery.config_from_object('celeryconfig')
client = MongoClient(c.MONGO_HOST, c.MONGO_PORT)
db = client[c.MONGO_DB]
tasks_collection = db["tasks"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я твой планировщик задач. Используй /add_task <текст задачи> <ГГГГ-ММ-ДД ЧЧ:ММ> для добавления задачи с дедлайном, /view_tasks для просмотра задач, /delete_task <task_id> для удаления задачи.")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Пожалуйста, введите текст задачи и дедлайн в формате ГГГГ-ММ-ДД ЧЧ:ММ. Например: /add_task Купить хлеб 2024-12-31 23:59")
            return

        task_text = ' '.join(context.args[:-1])
        deadline_str = context.args[-1]  # Последний аргумент - дедлайн

        try:
            deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')  # Формат: YYYY-MM-DD HH:MM
        except ValueError:
            await update.message.reply_text("Неправильный формат дедлайна. Используйте ГГГГ-ММ-ДД ЧЧ:ММ. Например: 2024-12-31 23:59")
            return

    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {e}. Пожалуйста, попробуйте еще раз.")
        return

    task = {
        "user_id": update.message.chat_id,
        "text": task_text,
        "deadline": deadline,
        "created_at": datetime.datetime.now()
    }

    try:
        result = tasks_collection.insert_one(task)
        task_id = result.inserted_id
        await update.message.reply_text(f"Задача добавлена с дедлайном {deadline.strftime('%Y-%m-%d %H:%M')}!")

        # Настраиваем напоминание
        reminder_time = deadline - datetime.timedelta(minutes=10)  # Напоминание за 10 минут до дедлайна
        if reminder_time > datetime.datetime.now():
            t.send_reminder.apply_async(args=[str(task_id)], eta=reminder_time)
            print(f"Напоминание запланировано для задачи {task_id} на {reminder_time}")

        # Проверка продления
        prolongation_time = deadline
        t.prolongate_deadline.apply_async(args=[str(task_id)], eta=prolongation_time)
        print(f"Проверка продления запланирована для задачи {task_id} на {prolongation_time}")

    except Exception as e:
        await update.message.reply_text(f"Не удалось добавить задачу: {e}")

# async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         task_text = ' '.join(context.args[:-1])
#         deadline_str = context.args[-1]  # Последний аргумент - дедлайн
#         deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')  # Формат: YYYY-MM-DD HH:MM
#     except (IndexError, ValueError):
#         await update.message.reply_text("Пожалуйста, введите текст задачи и дедлайн в формате ГГГГ-ММ-ДД ЧЧ:ММ. Например: /add_task Купить хлеб 2024-12-31 23:59")
#         return

#     task = {
#         "user_id": update.message.chat_id,
#         "text": task_text,
#         "deadline": deadline,
#         "created_at": datetime.datetime.now()
#     }

#     result = tasks_collection.insert_one(task)
#     task_id = result.inserted_id
#     await update.message.reply_text(f"Задача добавлена с дедлайном {deadline.strftime('%Y-%m-%d %H:%M')}!")

#     reminder_time = deadline - datetime.timedelta(minutes=10)  # Напоминание за 10 минут до дедлайна
#     if reminder_time > datetime.datetime.now():
#         t.send_reminder.apply_async(args=[str(task_id)], eta=reminder_time)
#         print(f"Reminder scheduled for task {task_id} at {reminder_time}")

#     prolongation_time = deadline
#     t.prolongate_deadline.apply_async(args=[str(task_id)], eta=prolongation_time)
#     print(f"Prolongation check scheduled for task {task_id} at {prolongation_time}")

async def view_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    tasks = tasks_collection.find({"user_id": user_id}).sort("deadline", 1)

    task_list = ""
    for task in tasks:
        time_left = task['deadline'] - datetime.datetime.now()
        status = "Просрочена!" if time_left < datetime.timedelta(0) else f"{time_left}"
        task_list += f"- {task['text']} (Дедлайн: {task['deadline'].strftime('%Y-%m-%d %H:%M')}, Статус: {status})\n"

    if task_list:
        await update.message.reply_text(f"Ваши задачи:\n{task_list}")
    else:
        await update.message.reply_text("Нет задач.")

async def delete_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = context.args[0]
        result = tasks_collection.delete_one({"_id": ObjectId(task_id), "user_id": update.message.chat_id})
        if result.deleted_count:
            await update.message.reply_text("Задача удалена!")
        else:
            await update.message.reply_text("Задача не найдена.")
    except (IndexError, ValueError):
        await update.message.reply_text("Пожалуйста, укажите ID задачи, которую нужно удалить. Например: /delete_task 654....")
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка при удалении задачи: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(c.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_task", add_task))
    app.add_handler(CommandHandler("view_tasks", view_tasks))
    app.add_handler(CommandHandler("delete_tasks", delete_tasks))

    app.run_polling()

