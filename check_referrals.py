from database import users_col

def check_referrals():
    # Find all users who have more than 0 referrals
    users_with_referrals = list(users_col.find(
        {"referral_count": {"$gt": 0}}, 
        {"user_id": 1, "first_name": 1, "username": 1, "referral_count": 1, "referral_points": 1, "_id": 0}
    ))
    
    print(f"Total users with at least 1 referral: {len(users_with_referrals)}")
    print("-" * 50)
    
    if not users_with_referrals:
        print("No users have any referrals yet.")
        return

    # Sort users by referral count (highest first)
    users_with_referrals.sort(key=lambda x: x.get("referral_count", 0), reverse=True)
    
    for user in users_with_referrals:
        username = f"@{user['username']}" if user.get('username') else "No Username"
        print(f"User: {user.get('first_name', 'Unknown')} ({username} | ID: {user['user_id']})")
        print(f"   -> Referrals: {user.get('referral_count', 0)}")
        print(f"   -> Points: {user.get('referral_points', 0)}")
        print("-" * 50)

if __name__ == "__main__":
    check_referrals()
