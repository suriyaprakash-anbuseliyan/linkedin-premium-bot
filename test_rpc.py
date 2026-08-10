import requests

def verify_bep20_deposit_rpc(tx_hash, expected_amount, expected_to_address):
    rpc_url = "https://bsc-dataseed.binance.org/"
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
        "id": 1
    }
    
    r = requests.post(rpc_url, json=payload, timeout=10)
    data = r.json()
    receipt = data.get("result")
    
    if not receipt:
        print("No receipt found.")
        return False
        
    if receipt.get("status") != "0x1":
        print("Transaction failed.")
        return False
        
    # USDT contract on BSC
    USDT_CONTRACT = "0x55d398326f99059ff775485246999027b3197955".lower()
    
    # Transfer event signature
    TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    
    expected_to_padded = "0x" + expected_to_address.lower().replace("0x", "").zfill(64)
    
    for log in receipt.get("logs", []):
        if log.get("address", "").lower() == USDT_CONTRACT:
            topics = log.get("topics", [])
            if len(topics) >= 3 and topics[0] == TRANSFER_TOPIC:
                to_address = topics[2].lower()
                if to_address == expected_to_padded:
                    value_hex = log.get("data", "0x0")
                    amount = int(value_hex, 16) / (10 ** 18)
                    print(f"Found transfer of {amount} USDT to {expected_to_address}")
                    if amount >= expected_amount - 0.01:
                        return True
                    else:
                        print(f"Amount mismatch. Expected {expected_amount}, got {amount}")
                        return False
                        
    print("No matching transfer log found.")
    return False

print(verify_bep20_deposit_rpc("0x46baf9e1dc83f98f98672a2d3b567479e0c9705e91926a8d0e136482b3f32d99", 4.9, "0xE639ABdeb0cc78200b420416d66c679f107eFBd2"))
