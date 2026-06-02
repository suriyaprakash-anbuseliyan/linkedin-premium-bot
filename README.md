# 🎯 LinkedIn Premium Store Bot

A production-ready Telegram bot for selling LinkedIn Premium referral/benefit links using a credit-based system with MongoDB Atlas as the database.

**Bot:** [@linkedinpremiumstore_bot](https://t.me/linkedinpremiumstore_bot)

---

## ✨ Features

| Feature | Description |
|---|---|
| **Mandatory Join** | Users must join a channel/group before accessing the bot |
| **Credit System** | Users purchase credits via UPI or Binance, then spend them on products |
| **Product Store** | Admin-configurable products with automatic delivery |
| **Payment System** | UPI & Binance with admin approval workflow |
| **Referral Program** | Every 3 referrals = 1 free credit (max 10) |
| **Admin Panel** | Full CRUD for products, payments, users, credits, broadcast, and stats |
| **Order History** | Users can view their past purchases |

---

## 📁 Project Structure

```
project/
├── bot.py                  # Entry point — starts polling
├── config.py               # Environment variables & constants
├── database.py             # MongoDB connection, collections, CRUD helpers
├── handlers/
│   ├── __init__.py         # Handler registration hub
│   ├── start.py            # /start, join gate, auto-registration
│   ├── menu.py             # Main menu callback router
│   ├── products.py         # Product browsing & purchasing
│   ├── credits.py          # Credit package selection & payment flow
│   ├── profile.py          # User profile page
│   ├── referral.py         # Referral info & stats
│   ├── orders.py           # Order history
│   ├── support.py          # Support / help page
│   ├── admin.py            # Admin panel & callbacks
│   └── states_handler.py   # Multi-step form text handler (catch-all)
├── keyboards/
│   ├── __init__.py
│   └── inline.py           # All inline keyboard factories
├── utils/
│   ├── __init__.py
│   ├── helpers.py          # Referral codes, admin checks, membership
│   └── states.py           # In-memory user state machine
├── requirements.txt
├── Procfile                # Railway deployment
├── .env.example            # Environment variable template
└── README.md               # This file
```

---

## 🚀 Setup & Deployment

### Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A MongoDB Atlas cluster (free tier works)

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd Linkedinbot
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token from BotFather |
| `MONGO_URI` | ✅ | MongoDB Atlas connection string |
| `ADMIN_ID` | ✅ | Your Telegram user ID |
| `REQUIRED_CHANNEL_USERNAME` | ⬜ | Channel username (without @) |
| `REQUIRED_CHANNEL_LINK` | ⬜ | Invite link for the channel |
| `UPI_ID` | ⬜ | UPI payment ID |
| `UPI_NAME` | ⬜ | UPI account name |
| `BINANCE_UID` | ⬜ | Binance user ID |

### 3. Make the Bot Admin of Your Channel

If you set `REQUIRED_CHANNEL_USERNAME`, the bot must be an **admin** of that channel/group so it can check membership via `getChatMember`.

### 4. Run Locally

```bash
python bot.py
```

### 5. Deploy to Railway

1. Push to a GitHub repo
2. Connect the repo to [Railway](https://railway.app)
3. Add environment variables in Railway dashboard
4. Railway auto-detects the `Procfile` and runs `worker: python bot.py`

---

## 🔧 Admin Commands

| Command | Description |
|---|---|
| `/admin` | Open the admin panel |
| `/start` | Regular user start (works for admin too) |

### Admin Panel Features

- ➕ **Add Product** — 4-step form (name, description, cost, delivery content)
- 📋 **Manage Products** — Enable/disable/delete products
- ✅ **Pending Payments** — Approve or reject with one tap
- 📦 **Orders** — View recent orders
- 👥 **Users** — Search by Telegram ID
- ➕/➖ **Credits** — Manually add/remove credits for any user
- 📢 **Broadcast** — Send a message to all users
- 📊 **Statistics** — Total users, products, orders, payments, credits sold

---

## 💳 Payment Flow

```
User selects package → Chooses UPI or Binance → Sees payment details →
Enters UTR / Order ID → Bot confirms submission → Admin gets notified →
Admin approves/rejects → User gets notified + credits added
```

---

## 🎁 Referral System

- Each user gets a unique referral link: `https://t.me/linkedinpremiumstore_bot?start=REF_CODE`
- Every **3** successful referrals → **+1 free credit**
- Maximum **10** free referral credits per user
- No self-referrals or duplicate referrals

---

## 📦 Database Collections

| Collection | Purpose |
|---|---|
| `users` | User profiles, credits, referral data |
| `products` | Store products with delivery content |
| `payments` | Payment requests with approval status |
| `orders` | Purchase history |

All collections are indexed for fast queries.

---

## 🛡️ Security

- Admin-only commands are gated by `ADMIN_ID`
- Mandatory join check on every major action
- Input validation on all forms
- Error handling with logging throughout

---

## 📄 License

Private — All rights reserved.
