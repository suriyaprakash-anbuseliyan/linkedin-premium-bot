from database import users_col, payments_col
from pprint import pprint

user = users_col.find_one({"username": "RAJESHTUNWAL"})
print("User by username:")
pprint(user)
if user:
    print("\nPayments by ID:")
    for p in payments_col.find({"user_id": user["_id"]}):
        pprint(p)
