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
    from config import BSCSCAN_API_KEY, BEP20_ADDRESS
    
    # Etherscan API V2 Endpoint for BEP-20 (BSC chainid=56) token transfers
    url = "https://api.etherscan.io/v2/api"
    params = {
        "chainid": 56,
        "module": "account",
        "action": "tokentx",
        "address": BEP20_ADDRESS,
        "page": 1,
        "offset": 50,  # check the last 50 transactions
        "sort": "desc",
        "apikey": BSCSCAN_API_KEY
    }
    
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        
        if data.get("status") == "1" and isinstance(data.get("result"), list):
            for tx in data["result"]:
                # Check if hash matches
                if tx.get("hash", "").lower() == tx_id.lower():
                    # Verify recipient is exactly our address
                    if tx.get("to", "").lower() != BEP20_ADDRESS.lower():
                        logger.warning("BEP-20 mismatch: 'to' address %s != %s", tx.get("to"), BEP20_ADDRESS)
                        return False
                        
                    # Verify token is USDT (Binance-Peg BSC-USD)
                    if tx.get("tokenSymbol", "").upper() != "USDT":
                        logger.warning("BEP-20 token mismatch: expected USDT, got %s", tx.get("tokenSymbol"))
                        return False
                        
                    # Token amounts are usually 18 decimals on BSC for USDT
                    token_decimals = int(tx.get("tokenDecimal", 18))
                    value_wei = float(tx.get("value", 0))
                    amount = value_wei / (10 ** token_decimals)
                    
                    if amount >= expected_amount - 0.01:
                        logger.info("BEP-20 transaction %s verified successfully.", tx_id)
                        return True
                    else:
                        logger.warning("BEP-20 Amount mismatch: expected %s USDT, got %s", expected_amount, amount)
                        return False
            
            logger.warning("BEP-20 transaction %s not found in recent deposits.", tx_id)
        else:
            logger.error("BscScan API returned error/empty: %s", data.get("message"))
            
        return False
    except Exception as e:
        logger.error("Failed to query BscScan API for deposits: %s", e)
        return False

def verify_trc20_deposit_transaction(tx_id: str, expected_amount: float) -> bool:
    from config import TRONGRID_API_KEY, TRC20_ADDRESS
    
    # TronGrid API Endpoint for TRC-20 token transfers
    url = f"https://api.trongrid.io/v1/accounts/{TRC20_ADDRESS}/transactions/trc20"
    
    # Tron USDT contract address
    TRON_USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    
    params = {
        "limit": 50,
        "contract_address": TRON_USDT_CONTRACT,
    }
    
    headers = {
        "Accept": "application/json"
    }
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY
        
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        
        if data.get("success") and isinstance(data.get("data"), list):
            for tx in data["data"]:
                if tx.get("transaction_id", "").lower() == tx_id.lower():
                    # Verify recipient is exactly our address
                    if tx.get("to", "") != TRC20_ADDRESS:
                        logger.warning("TRC-20 mismatch: 'to' address %s != %s", tx.get("to"), TRC20_ADDRESS)
                        return False
                        
                    # Verify token is USDT
                    if tx.get("token_info", {}).get("symbol", "").upper() != "USDT":
                        logger.warning("TRC-20 token mismatch: expected USDT")
                        return False
                        
                    # TRC20 USDT has 6 decimals
                    token_decimals = int(tx.get("token_info", {}).get("decimals", 6))
                    value_mwei = float(tx.get("value", 0))
                    amount = value_mwei / (10 ** token_decimals)
                    
                    if amount >= expected_amount - 0.01:
                        logger.info("TRC-20 transaction %s verified successfully.", tx_id)
                        return True
                    else:
                        logger.warning("TRC-20 Amount mismatch: expected %s USDT, got %s", expected_amount, amount)
                        return False
            
            logger.warning("TRC-20 transaction %s not found in recent deposits.", tx_id)
        else:
            logger.error("TronGrid API returned error/empty: %s", data)
            
        return False
    except Exception as e:
        logger.error("Failed to query TronGrid API for deposits: %s", e)
        return False

