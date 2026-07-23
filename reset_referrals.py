import json
from database import users_col, settings_col

def backup_and_reset():
    # 1. Backup users as per the rule: "Always create backups before destructive data migrations"
    users = list(users_col.find({}, {"_id": 0}))
    with open('users_backup.json', 'w') as f:
        json.dump(users, f, default=str)
    print(f"Backed up {len(users)} users to users_backup.json")

    # 2. Reset referral_points and free_referral_bonus (keep referral_count!)
    result = users_col.update_many(
        {},
        {"$set": {"referral_points": 0, "free_referral_bonus": 0.0}}
    )
    print(f"Reset referral points and bonus for {result.modified_count} users.")

    # 3. Delete old referral_config so it defaults to the new 5.00 limit
    settings_col.delete_one({"_id": "referral_config"})
    print("Deleted old referral_config to apply new defaults.")

if __name__ == "__main__":
    backup_and_reset()
