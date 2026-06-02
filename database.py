"""
database.py
───────────
MongoDB connection helper and collection accessors.
Creates indexes on first import so queries stay fast.
"""

from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from config import MONGO_URI, DB_NAME, logger

# ── Connection ───────────────────────────────────────────────────────────
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# ── Collections ──────────────────────────────────────────────────────────
users_col = db["users"]
products_col = db["products"]
payments_col = db["payments"]
orders_col = db["orders"]
stock_col = db["stock"]
settings_col = db["settings"]
gift_codes_col = db["gift_codes"]


# ── Indexes (idempotent – safe to call on every startup) ─────────────────
def ensure_indexes() -> None:
    """Create MongoDB indexes for fast lookups."""
    users_col.create_index([("user_id", ASCENDING)], unique=True)
    users_col.create_index([("referral_code", ASCENDING)], unique=True)

    products_col.create_index([("active", ASCENDING)])
    products_col.create_index([("created_at", DESCENDING)])

    payments_col.create_index([("user_id", ASCENDING)])
    payments_col.create_index([("status", ASCENDING)])
    payments_col.create_index([("created_at", DESCENDING)])

    orders_col.create_index([("user_id", ASCENDING)])
    orders_col.create_index([("created_at", DESCENDING)])

    stock_col.create_index([("product_id", ASCENDING), ("is_sold", ASCENDING)])
    stock_col.create_index([("product_id", ASCENDING)])

    gift_codes_col.create_index([("code", ASCENDING)], unique=True)

    logger.info("MongoDB indexes ensured.")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  USER helpers                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

def get_user(user_id: int) -> dict | None:
    return users_col.find_one({"user_id": user_id})


def register_user(user_id: int, username: str, first_name: str,
                   referral_code: str, referred_by: str | None = None) -> dict:
    """Insert a new user document. Returns the inserted doc."""
    doc = {
        "user_id": user_id,
        "username": username or "",
        "first_name": first_name or "",
        "credits": 0,
        "referral_code": referral_code,
        "referred_by": referred_by,
        "referral_count": 0,
        "referral_points": 1,
        "free_referral_credits": 0,
        "joined_at": datetime.now(timezone.utc),
    }
    users_col.insert_one(doc)
    return doc


def update_user(user_id: int, update: dict) -> None:
    users_col.update_one({"user_id": user_id}, update)


def add_credits(user_id: int, amount: int) -> None:
    users_col.update_one({"user_id": user_id}, {"$inc": {"credits": amount}})


def remove_credits(user_id: int, amount: int) -> None:
    users_col.update_one({"user_id": user_id}, {"$inc": {"credits": -amount}})


def increment_referral_count(user_id: int) -> dict | None:
    """Increment referral_count and points, return the updated document."""
    return users_col.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"referral_count": 1, "referral_points": 1}},
        return_document=True,
    )


def redeem_referral_points(user_id: int, points_cost: int) -> bool:
    """
    Atomically deduct points_cost and add 1 credit.
    Returns True if successful, False if insufficient points.
    """
    result = users_col.update_one(
        {"user_id": user_id, "referral_points": {"$gte": points_cost}},
        {"$inc": {"credits": 1, "free_referral_credits": 1, "referral_points": -points_cost}},
    )
    return result.modified_count > 0


def get_all_user_ids() -> list[int]:
    """Return list of all user_ids (for broadcasts)."""
    return [u["user_id"] for u in users_col.find({}, {"user_id": 1})]


def get_user_by_referral_code(code: str) -> dict | None:
    return users_col.find_one({"referral_code": code})


def count_users() -> int:
    return users_col.count_documents({})


def search_user_by_id(user_id: int) -> dict | None:
    return get_user(user_id)


def ban_user(user_id: int, ban: bool) -> None:
    """Ban or unban a user by setting is_banned."""
    users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": ban}})


def delete_user(user_id: int) -> None:
    """Delete a user permanently."""
    users_col.delete_one({"user_id": user_id})


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PRODUCT helpers                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

def create_product(name: str, description: str, credit_cost: int) -> str:
    """Insert a product and return its _id as string."""
    doc = {
        "name": name,
        "description": description,
        "credit_cost": credit_cost,
        "active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = products_col.insert_one(doc)
    return str(result.inserted_id)


def get_active_products() -> list[dict]:
    return list(products_col.find({"active": True}).sort("created_at", DESCENDING))


def get_product(product_id) -> dict | None:
    from bson import ObjectId
    return products_col.find_one({"_id": ObjectId(product_id)})


def get_all_products() -> list[dict]:
    return list(products_col.find().sort("created_at", DESCENDING))


def update_product(product_id, update: dict) -> None:
    from bson import ObjectId
    products_col.update_one({"_id": ObjectId(product_id)}, update)


def delete_product(product_id) -> None:
    from bson import ObjectId
    products_col.delete_one({"_id": ObjectId(product_id)})


def count_products() -> int:
    return products_col.count_documents({"active": True})


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  STOCK / INVENTORY helpers                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

def add_stock_items(product_id: str, links: list[str]) -> int:
    """Bulk-insert stock items for a product. Returns count inserted."""
    from bson import ObjectId
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    docs = [
        {
            "product_id": ObjectId(product_id),
            "content": link.strip(),
            "is_sold": False,
            "sold_to": None,
            "sold_at": None,
            "added_at": now,
            "expires_at": expires_at,
        }
        for link in links if link.strip()
    ]
    if not docs:
        return 0
    result = stock_col.insert_many(docs)
    return len(result.inserted_ids)


def get_available_stock_count(product_id: str) -> int:
    """Count unsold stock items for a product."""
    from bson import ObjectId
    return stock_col.count_documents({
        "product_id": ObjectId(product_id),
        "is_sold": False,
    })


def get_total_stock_count(product_id: str) -> int:
    """Count all stock items (sold + unsold) for a product."""
    from bson import ObjectId
    return stock_col.count_documents({"product_id": ObjectId(product_id)})


def claim_stock_item(product_id: str, user_id: int) -> dict | None:
    """
    Atomically claim one unsold stock item for a user.
    Returns the stock document (with content) or None if out of stock.
    """
    from bson import ObjectId
    return stock_col.find_one_and_update(
        {"product_id": ObjectId(product_id), "is_sold": False},
        {"$set": {"is_sold": True, "sold_to": user_id, "sold_at": datetime.now(timezone.utc)}},
    )


def delete_product_stock(product_id: str) -> int:
    """Delete all stock items for a product. Returns count deleted."""
    from bson import ObjectId
    result = stock_col.delete_many({"product_id": ObjectId(product_id)})
    return result.deleted_count


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAYMENT helpers                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

def create_payment(user_id: int, username: str, method: str, amount: float,
                   credits: int, utr_number: str | None = None,
                   binance_order_id: str | None = None) -> str:
    """Insert a payment request. Returns the _id as string."""
    doc = {
        "user_id": user_id,
        "username": username or "",
        "method": method,
        "amount": amount,
        "credits": credits,
        "utr_number": utr_number,
        "binance_order_id": binance_order_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "reviewed_at": None,
    }
    result = payments_col.insert_one(doc)
    return str(result.inserted_id)


def check_binance_order_exists(binance_order_id: str) -> bool:
    """Check if a Binance Order ID has already been submitted."""
    return payments_col.count_documents({"binance_order_id": binance_order_id}) > 0


def get_pending_payments() -> list[dict]:
    return list(payments_col.find({"status": "pending"}).sort("created_at", ASCENDING))


def approve_payment(payment_id) -> dict | None:
    from bson import ObjectId
    return payments_col.find_one_and_update(
        {"_id": ObjectId(payment_id)},
        {"$set": {"status": "approved", "reviewed_at": datetime.now(timezone.utc)}},
        return_document=True,
    )


def reject_payment(payment_id) -> dict | None:
    from bson import ObjectId
    return payments_col.find_one_and_update(
        {"_id": ObjectId(payment_id)},
        {"$set": {"status": "rejected", "reviewed_at": datetime.now(timezone.utc)}},
        return_document=True,
    )


def count_payments() -> int:
    return payments_col.count_documents({})


def total_credits_sold() -> int:
    """Sum of credits from all approved payments."""
    pipeline = [
        {"$match": {"status": "approved"}},
        {"$group": {"_id": None, "total": {"$sum": "$credits"}}},
    ]
    result = list(payments_col.aggregate(pipeline))
    return result[0]["total"] if result else 0


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ORDER helpers                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

def create_order(user_id: int, product_name: str, credits_used: int) -> str:
    doc = {
        "user_id": user_id,
        "product_name": product_name,
        "credits_used": credits_used,
        "created_at": datetime.now(timezone.utc),
    }
    result = orders_col.insert_one(doc)
    return str(result.inserted_id)


def get_user_orders(user_id: int) -> list[dict]:
    return list(orders_col.find({"user_id": user_id}).sort("created_at", DESCENDING))


def count_orders() -> int:
    return orders_col.count_documents({})


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SETTINGS helpers (runtime-editable config)                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

def get_setting(key: str, default: str = "") -> str:
    """Get a setting value from DB. Falls back to *default* if not set."""
    doc = settings_col.find_one({"key": key})
    if doc:
        return doc.get("value", default)
    return default


def set_setting(key: str, value: str) -> None:
    """Upsert a setting value in DB."""
    settings_col.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value}},
        upsert=True,
    )


def get_payment_settings() -> dict:
    doc = settings_col.find_one({"_id": "payment_settings"})
    if not doc:
        from config import UPI_ID, UPI_NAME, BINANCE_UID
        return {"upi_id": UPI_ID, "upi_name": UPI_NAME, "binance_uid": BINANCE_UID}
    return doc


def update_payment_settings(upi_id: str, upi_name: str, binance_uid: str) -> None:
    settings_col.update_one(
        {"_id": "payment_settings"},
        {"$set": {"upi_id": upi_id, "upi_name": upi_name, "binance_uid": binance_uid}},
        upsert=True
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  MAINTENANCE MODE helpers                                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

def is_maintenance_mode() -> bool:
    doc = settings_col.find_one({"_id": "maintenance_mode"})
    return doc.get("enabled", False) if doc else False


def set_maintenance_mode(enabled: bool) -> None:
    settings_col.update_one(
        {"_id": "maintenance_mode"},
        {"$set": {"enabled": enabled}},
        upsert=True
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  GIFT CODES helpers                                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

def create_gift_code(code: str, credits_value: int, max_uses: int, expires_at: datetime | None, created_by: int) -> None:
    """Creates a new gift code."""
    doc = {
        "code": code,
        "credits": credits_value,
        "max_uses": max_uses,
        "current_uses": 0,
        "expires_at": expires_at,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc),
        "redeemed_by": []  # List of user_ids who have redeemed it
    }
    gift_codes_col.insert_one(doc)


def get_gift_code(code: str) -> dict | None:
    """Retrieve a gift code by its code string."""
    return gift_codes_col.find_one({"code": code})


def redeem_gift_code(code: str, user_id: int) -> bool | str:
    """
    Attempts to redeem a gift code for a user.
    Returns True if successful. Returns error string if it fails.
    """
    code_doc = gift_codes_col.find_one({"code": code})
    if not code_doc:
        return "Invalid code."
        
    if code_doc["current_uses"] >= code_doc["max_uses"]:
        return "This code has reached its maximum usage limit."
        
    if code_doc["expires_at"] and datetime.now(timezone.utc) > code_doc["expires_at"].replace(tzinfo=timezone.utc):
        return "This code has expired."
        
    if user_id in code_doc.get("redeemed_by", []):
        return "You have already redeemed this code."
        
    # Atomically update usage and user credits
    result = gift_codes_col.update_one(
        {"_id": code_doc["_id"], "current_uses": {"$lt": code_doc["max_uses"]}},
        {
            "$inc": {"current_uses": 1},
            "$push": {"redeemed_by": user_id}
        }
    )
    
    if result.modified_count == 1:
        # Give credits
        users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"credits": code_doc["credits"]}}
        )
        return True
        
    return "Failed to redeem code. Please try again."
