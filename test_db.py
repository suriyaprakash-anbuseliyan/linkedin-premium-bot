import os
import sys
sys.path.append("/home/ubuntu/.local/lib/python3.10/site-packages")
from dotenv import load_dotenv
load_dotenv("/home/ubuntu/linkedin-premium-bot/.env")
from pymongo import MongoClient
client = MongoClient(os.environ["MONGO_URI"])
db = client[os.environ.get("DB_NAME", "linkedin_premium_bot")]

orders = list(db.qr_orders.find({"status": "awaiting_qr"}))
for order in orders:
    print(f"Cancelling stuck order {order['_id']}")
    db.qr_orders.update_one({"_id": order["_id"]}, {"$set": {"status": "cancelled_admin"}})
    db.users.update_one({"user_id": order["user_id"]}, {"$inc": {"credits": order.get("credits_used", 0)}})
    
    # Refund stock
    pid_str = order.get("product_id")
    if pid_str:
        from bson import ObjectId
        pid = ObjectId(pid_str)
        if order.get("is_numerical"):
            db.products.update_one({"_id": pid}, {"$inc": {"numerical_stock": order.get("qty", 1)}})
        else:
            items = order.get("items", [])
            if items:
                db.stock.update_many({"product_id": pid, "content": {"$in": items}}, {"$set": {"is_sold": False, "sold_to": None, "sold_at": None}})

print("Cleanup done.")
