from utils.payments import verify_bep20_deposit_transaction
import requests
from config import BEP20_ADDRESS, BSCSCAN_API_KEY
url = "https://api.bscscan.com/api"
params = {
    "module": "account",
    "action": "tokentx",
    "address": BEP20_ADDRESS,
    "page": 1,
    "offset": 50,
    "sort": "desc",
    "apikey": BSCSCAN_API_KEY
}
r = requests.get(url, params=params)
print(r.json())
