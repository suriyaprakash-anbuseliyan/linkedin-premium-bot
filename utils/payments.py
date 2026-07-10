import requests
import time
import hmac
import hashlib
from config import BINANCE_API_KEY, BINANCE_API_SECRET, logger

def verify_binance_pay_transaction(order_id: str, expected_amount: float) -> bool:
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
                    # Note check removed by user request
                        
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

def verify_bep20_deposit_transaction(tx_id: str, expected_amount: float) -> bool:
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.warning("Binance API keys not configured.")
        return False
        
    url = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
    
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
        
        # 'data' is a list of deposits if successful
        if isinstance(data, list):
            for tx in data:
                # Binance returns txId in the array
                if tx.get("txId") == tx_id:
                    # Check currency
                    currency = tx.get("coin", "")
                    if currency != "USDT":
                        logger.warning("BEP-20 Currency mismatch: expected USDT, got %s", currency)
                        return False
                        
                    # Check network
                    network = tx.get("network", "")
                    if network != "BSC": # BSC is the identifier for BEP-20
                        logger.warning("BEP-20 Network mismatch: expected BSC, got %s", network)
                        return False
                        
                    # Check status (1: success)
                    status = tx.get("status")
                    if status != 1:
                        logger.warning("BEP-20 Deposit not successful yet (status: %s)", status)
                        return False

                    # Check amount matches
                    amount = float(tx.get("amount", 0))
                        
                    if abs(amount - expected_amount) < 0.01:
                        logger.info("BEP-20 transaction %s verified successfully.", tx_id)
                        return True
                    else:
                        logger.warning("BEP-20 Amount mismatch: expected %s USDT, got %s", expected_amount, amount)
                        return False
            logger.warning("BEP-20 transaction %s not found in recent deposits.", tx_id)
        else:
            logger.error("Binance API returned error for deposits: %s", data)
        return False
    except Exception as e:
        logger.error("Failed to query Binance API for deposits: %s", e)
        return False
