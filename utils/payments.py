import razorpay
import requests
import time
import hmac
import hashlib
import json
import string
import random
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, BINANCE_API_KEY, BINANCE_API_SECRET, logger

# -- Razorpay --
rzp_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_razorpay_payment_link(amount_inr: int, reference_id: str, description: str) -> dict | None:
    """Returns a dict containing 'id' (payment link ID) and 'short_url'."""
    if not rzp_client:
        return None
        
    try:
        data = {
            "amount": amount_inr * 100, # Amount in paise
            "currency": "INR",
            "accept_partial": False,
            "description": description,
            "reference_id": reference_id,
            "reminder_enable": False,
        }
        logger.info("Creating Razorpay link: %s", data)
        res = rzp_client.payment_link.create(data)
        logger.info("Razorpay link created: %s", res)
        return {
            "id": res["id"],
            "short_url": res["short_url"]
        }
    except Exception as e:
        logger.error("Failed to create Razorpay link: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        return None

def verify_razorpay_payment(payment_link_id: str) -> bool:
    if not rzp_client:
        return False
    try:
        res = rzp_client.payment_link.fetch(payment_link_id)
        return res.get("status") == "paid"
    except Exception as e:
        logger.error("Failed to verify Razorpay link: %s", e)
        return False

def verify_binance_pay_transaction(order_id: str, expected_amount: float, expected_note: str) -> bool:
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.warning("Binance API keys not configured.")
        return False
        
    url = "https://api.binance.com/sapi/v1/pay/transactions"
    
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    
    signature = hmac.new(
        BINANCE_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    query_string += f"&signature={signature}"
    full_url = f"{url}?{query_string}"
    
    headers = {
        "X-MBX-APIKEY": BINANCE_API_KEY
    }
    
    try:
        r = requests.get(full_url, headers=headers, timeout=10)
        data = r.json()
        
        # 'data' contains list of transactions if code is 000000
        if data.get("code") == "000000" and "data" in data:
            transactions = data["data"]
            for tx in transactions:
                # Binance Pay transaction ID is usually orderId or transactionId
                if tx.get("orderId") == order_id or tx.get("transactionId") == order_id:
                    # Check if the note matches
                    actual_note = tx.get("note", "").strip()
                    if actual_note.lower() != expected_note.lower():
                        logger.warning("Binance Pay Note mismatch: expected %s, got %s", expected_note, actual_note)
                        return False
                        
                    # Check amount matches
                    amount = 0.0
                    currency = ""
                    funds = tx.get("fundsDetail", [])
                    if funds:
                        amount = float(funds[0].get("amount", 0))
                        currency = funds[0].get("currency", "")
                    else:
                        amount = float(tx.get("amount", 0))
                        currency = tx.get("currency", "")
                        
                    if currency == "USDT" and abs(amount - expected_amount) < 0.01:
                        logger.info("Binance Pay transaction %s verified successfully.", order_id)
                        return True
                    else:
                        logger.warning("Binance Pay Amount/Currency mismatch: expected %s USDT, got %s %s", expected_amount, amount, currency)
                        return False
            logger.warning("Binance Pay transaction %s not found in the recent history.", order_id)
        else:
            logger.error("Binance API returned error: %s", data)
        return False
    except Exception as e:
        logger.error("Failed to query Binance API: %s", e)
        return False
