from database import payments_col
from datetime import datetime, timezone

tx_hash = "0x46baf9e1dc83f98f98672a2d3b567479e0c9705e91926a8d0e136482b3f32d99"
doc = {
    "user_id": 0,
    "method": "BEP-20",
    "amount_usd": 5.0,
    "status": "approved", # Or whatever status prevents reuse
    "utr_number": None,
    "binance_order_id": tx_hash, # This is the field check_binance_order_exists checks
    "screenshot_id": None,
    "created_at": datetime.now(timezone.utc),
    "auto_verified": True
}
payments_col.insert_one(doc)
print("Transaction ID blocked.")
