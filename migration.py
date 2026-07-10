import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "linkedin_premium_bot")

if not MONGO_URI:
    print("MONGO_URI is missing")
    exit(1)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

print("Starting migration...")

# 1. Migrate Users
users_col = db["users"]
user_count = 0
for user in users_col.find():
    update_fields = {}
    
    # Migrate credits to wallet_balance
    if "credits" in user:
        credits = user["credits"]
        wallet_balance = float(credits * 0.5)  # 2 credits = $1, so 1 credit = $0.5
        update_fields["wallet_balance"] = wallet_balance
        update_fields["credits"] = 0 # keep around just in case but empty it
        
    if "free_referral_credits" in user:
        free_credits = user["free_referral_credits"]
        wallet_balance_bonus = float(free_credits * 0.5)
        update_fields["free_referral_bonus"] = wallet_balance_bonus
        update_fields["free_referral_credits"] = 0
        
    if update_fields:
        users_col.update_one({"_id": user["_id"]}, {"$set": update_fields})
        user_count += 1

print(f"Migrated {user_count} users to wallet_balance.")

# 2. Migrate Products
products_col = db["products"]
product_count = 0
for product in products_col.find():
    update_fields = {}
    
    if "credit_cost" in product:
        credit_cost = product["credit_cost"]
        price_usd = float(credit_cost * 0.5)
        update_fields["price_usd"] = price_usd
        update_fields["credit_cost"] = 0
        
    if update_fields:
        products_col.update_one({"_id": product["_id"]}, {"$set": update_fields})
        product_count += 1

print(f"Migrated {product_count} products to price_usd.")

# 3. Migrate Orders
orders_col = db["orders"]
order_count = 0
for order in orders_col.find():
    update_fields = {}
    if "credits_used" in order:
        credits_used = order["credits_used"]
        price_paid = float(credits_used * 0.5)
        update_fields["price_paid_usd"] = price_paid
        
    if update_fields:
        orders_col.update_one({"_id": order["_id"]}, {"$set": update_fields})
        order_count += 1
        
print(f"Migrated {order_count} orders to price_paid_usd.")

print("Migration completed successfully!")
