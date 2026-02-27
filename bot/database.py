from pymongo import MongoClient
from config import MONGODB_URI, DB_NAME
from datetime import datetime

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

users_col = db["users"]
messages_col = db["messages"]


def save_user(user):
    users_col.update_one(
        {"user_id": user.id},
        {"$set": {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "joined_at": datetime.utcnow()
        }},
        upsert=True
    )


def get_all_users():
    return list(users_col.find({}, {"_id": 0, "user_id": 1}))


def save_message(from_user_id, text, direction="incoming"):
    messages_col.insert_one({
        "from_user_id": from_user_id,
        "text": text,
        "direction": direction,
        "timestamp": datetime.utcnow()
    })


def get_stats():
    total_users = users_col.count_documents({})
    total_messages = messages_col.count_documents({"direction": "incoming"})
    return total_users, total_messages


def ban_user(user_id):
    users_col.update_one({"user_id": user_id}, {"$set": {"banned": True}})


def unban_user(user_id):
    users_col.update_one({"user_id": user_id}, {"$set": {"banned": False}})


def is_banned(user_id):
    user = users_col.find_one({"user_id": user_id})
    return user.get("banned", False) if user else False
