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
qr_orders_col = db["qr_orders"]


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
    stock_col.create_index([("content", ASCENDING)], unique=True, sparse=True)

    gift_codes_col.create_index([("code", ASCENDING)], unique=True)

    qr_orders_col.create_index([("user_id", ASCENDING)])
    qr_orders_col.create_index([("status", ASCENDING)])
    qr_orders_col.create_index([("created_at", DESCENDING)])

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

def create_product(name: str, description: str, credit_cost: int, is_numerical: bool = False, numerical_stock: int = 0) -> str:
    """Insert a product and return its _id as string."""
    doc = {
        "name": name,
        "description": description,
        "credit_cost": credit_cost,
        "active": True,
        "is_numerical": is_numerical,
        "numerical_stock": numerical_stock,
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

def get_existing_stock_links(links: list[str]) -> set[str]:
    """Return a set of links that already exist in stock (any product, sold or unsold)."""
    stripped = [l.strip() for l in links if l.strip()]
    if not stripped:
        return set()
    existing_docs = stock_col.find({"content": {"$in": stripped}}, {"content": 1})
    return {doc["content"] for doc in existing_docs}


def add_stock_items(product_id: str, links: list[str]) -> tuple[int, int]:
    """
    Bulk-insert stock items for a product, skipping duplicates.
    Returns (count_inserted, count_duplicates).
    """
    from bson import ObjectId
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)

    # Filter out links that already exist in any product's stock
    stripped_links = [link.strip() for link in links if link.strip()]
    existing = get_existing_stock_links(stripped_links)
    new_links = [l for l in stripped_links if l not in existing]
    duplicate_count = len(stripped_links) - len(new_links)

    docs = [
        {
            "product_id": ObjectId(product_id),
            "content": link,
            "is_sold": False,
            "sold_to": None,
            "sold_at": None,
            "added_at": now,
            "expires_at": expires_at,
        }
        for link in new_links
    ]
    if not docs:
        return 0, duplicate_count
    result = stock_col.insert_many(docs)
    return len(result.inserted_ids), duplicate_count


def get_available_stock_count(product_id: str) -> int:
    """Count unsold stock items for a product, or return numerical stock if applicable."""
    from bson import ObjectId
    product = products_col.find_one({"_id": ObjectId(product_id)})
    if product and product.get("is_numerical"):
        return product.get("numerical_stock", 0)

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

def create_order(user_id: int, product_name: str, credits_used: int, items: list[str] = None) -> str:
    doc = {
        "user_id": user_id,
        "product_name": product_name,
        "credits_used": credits_used,
        "items": items or [],
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
# ║  REFERRAL PROGRAM helpers                                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

def is_referral_enabled() -> bool:
    """Check if the referral program is enabled. Defaults to True."""
    doc = settings_col.find_one({"_id": "referral_program"})
    return doc.get("enabled", True) if doc else True


def set_referral_enabled(enabled: bool) -> None:
    """Enable or disable the referral program."""
    settings_col.update_one(
        {"_id": "referral_program"},
        {"$set": {"enabled": enabled}},
        upsert=True
    )


def get_referral_config() -> dict:
    """
    Get referral conversion config from DB.
    Falls back to config.py defaults if not set.
    Returns: {"points_per_credit": int, "max_free_credits": int}
    """
    from config import REFERRALS_PER_CREDIT, MAX_FREE_REFERRAL_CREDITS
    doc = settings_col.find_one({"_id": "referral_config"})
    if doc:
        return {
            "points_per_credit": doc.get("points_per_credit", REFERRALS_PER_CREDIT),
            "max_free_credits": doc.get("max_free_credits", MAX_FREE_REFERRAL_CREDITS),
        }
    return {
        "points_per_credit": REFERRALS_PER_CREDIT,
        "max_free_credits": MAX_FREE_REFERRAL_CREDITS,
    }


def set_referral_config(points_per_credit: int = None, max_free_credits: int = None) -> None:
    """Update referral conversion config. Only updates provided fields."""
    update = {}
    if points_per_credit is not None:
        update["points_per_credit"] = points_per_credit
    if max_free_credits is not None:
        update["max_free_credits"] = max_free_credits
    if update:
        settings_col.update_one(
            {"_id": "referral_config"},
            {"$set": update},
            upsert=True
        )


def is_credit_conversion_enabled() -> bool:
    """Check if points-to-credits conversion is enabled. Defaults to True."""
    doc = settings_col.find_one({"_id": "credit_conversion"})
    return doc.get("enabled", True) if doc else True


def set_credit_conversion_enabled(enabled: bool) -> None:
    """Enable or disable points-to-credits conversion."""
    settings_col.update_one(
        {"_id": "credit_conversion"},
        {"$set": {"enabled": enabled}},
        upsert=True
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  GIFT CODES helpers                                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

def create_gift_code(code: str, points_value: int, max_uses: int, expires_at: datetime | None, created_by: int) -> None:
    """Creates a new gift code that gives points."""
    doc = {
        "code": code,
        "points": points_value,
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
    Gift codes give points (referral_points), not credits.
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
        
    # Atomically update usage
    result = gift_codes_col.update_one(
        {"_id": code_doc["_id"], "current_uses": {"$lt": code_doc["max_uses"]}},
        {
            "$inc": {"current_uses": 1},
            "$push": {"redeemed_by": user_id}
        }
    )
    
    if result.modified_count == 1:
        # Give points (referral_points), not credits
        users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"referral_points": code_doc["points"]}}
        )
        return True
        
    return "Failed to redeem code. Please try again."

def search_database(query: str) -> dict:
    """Search for a link in stock_col or a code in gift_codes_col."""
    query = query.strip()
    result = {"type": "none", "data": None}
    
    # Check if query is a URL with a coupon
    search_term = query
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(query)
        if parsed.query:
            params = parse_qs(parsed.query)
            if "coupon" in params and params["coupon"]:
                search_term = params["coupon"][0].strip()
    except Exception:
        pass
    
    # 1. Search in stock
    stock_item = stock_col.find_one({"content": {"$regex": search_term, "$options": "i"}})
    if stock_item:
        result["type"] = "stock"
        result["data"] = stock_item
        return result
        
    # 2. Search in gift codes
    code_item = gift_codes_col.find_one({"code": query})
    if code_item:
        result["type"] = "gift_code"
        result["data"] = code_item
        return result
        
    return result

def update_ui_setting(button_key: str, field: str, value: str):
    """
    Update a specific field (text, style, emoji_id) for a button in the ui_buttons setting.
    """
    ui_settings = get_setting("ui_buttons", {})
    if button_key not in ui_settings:
        ui_settings[button_key] = {}
    
    ui_settings[button_key][field] = value
    
    # Save back to settings_col
    settings_col.update_one(
        {"key": "ui_buttons"},
        {"$set": {"key": "ui_buttons", "value": ui_settings}},
        upsert=True
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  QR ORDER helpers                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

def create_qr_order(user_id: int, product_name: str, credits_used: int,
                    items: list[str], order_id: str) -> str:
    """Create a QR order record after purchase. Returns the _id as string."""
    doc = {
        "user_id": user_id,
        "product_name": product_name,
        "credits_used": credits_used,
        "items": items or [],
        "order_id": order_id,
        "status": "awaiting_qr",  # awaiting_qr → qr_uploaded → approved/rejected/reupload
        "qr_file_id": None,
        "qr_file_unique_id": None,
        "uploaded_qr_ids": [],  # track all uploaded QR unique IDs to prevent duplicates
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    result = qr_orders_col.insert_one(doc)
    return str(result.inserted_id)


def get_qr_order(qr_order_id: str) -> dict | None:
    """Fetch a QR order by its _id."""
    from bson import ObjectId
    return qr_orders_col.find_one({"_id": ObjectId(qr_order_id)})


def update_qr_order_status(qr_order_id: str, status: str,
                           qr_file_id: str = None,
                           qr_file_unique_id: str = None) -> None:
    """Update a QR order's status and optionally its QR file info."""
    from bson import ObjectId
    update = {
        "$set": {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
    }
    if qr_file_id is not None:
        update["$set"]["qr_file_id"] = qr_file_id
        update["$set"]["qr_file_unique_id"] = qr_file_unique_id
    if qr_file_unique_id is not None:
        update.setdefault("$push", {})
        update["$push"]["uploaded_qr_ids"] = qr_file_unique_id
    qr_orders_col.update_one({"_id": ObjectId(qr_order_id)}, update)


def check_duplicate_qr(user_id: int, file_unique_id: str) -> bool:
    """Check if this QR image was already uploaded by this user in any QR order."""
    return qr_orders_col.count_documents({
        "user_id": user_id,
        "uploaded_qr_ids": file_unique_id,
    }) > 0
