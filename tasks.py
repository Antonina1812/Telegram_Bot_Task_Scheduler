from celery import Celery
from pymongo import MongoClient
import datetime
import telegram
import constants as c

celery = Celery('tasks', broker=c.CELERY_BROKER_URL, backend=c.CELERY_RESULT_BACKEND)
celery.config_from_object('celeryconfig')
client = MongoClient(c.MONGO_HOST, c.MONGO_PORT)
db = client[c.MONGO_DB]
tasks_collection = db["tasks"]

bot = telegram.Bot(token=c.TELEGRAM_TOKEN)

@celery.task
def send_reminder(task_id):
    task = tasks_collection.find_one({"_id": task_id})
    if task:
        user_id = task['user_id']
        task_text = task['text']
        bot.send_message(chat_id=user_id, text=f"Напоминание: {task_text}")
    else:
        print(f"Task with id {task_id} not found.")

@celery.task
def prolongate_deadline(task_id):
    task = tasks_collection.find_one({"_id": task_id})
    if task:
        if task['deadline'] < datetime.datetime.now():
            new_deadline = task['deadline'] + datetime.timedelta(days=1)
            tasks_collection.update_one({"_id": task_id}, {"$set": {"deadline": new_deadline}})
            user_id = task['user_id']
            task_text = task['text']
            bot.send_message(chat_id=user_id, text=f"Срок выполнения задачи '{task_text}' продлен на 1 день (до {new_deadline.strftime('%Y-%m-%d %H:%M')}).")
        else:
            print(f"Task with id {task_id} is not overdue.")
    else:
        print(f"Task with id {task_id} not found for prolongation.")