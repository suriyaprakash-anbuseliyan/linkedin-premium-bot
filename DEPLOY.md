# 🚀 Deployment Guide — LinkedIn Premium Bot

> **Rule:** After EVERY code change, you MUST deploy to the server.  
> The bot runs 24/7 on the Oracle Cloud server — not on your local Mac.

---

## 🖥️ Server Info

| Detail        | Value                                      |
|---------------|-------------------------------------------|
| **IP**        | `140.245.200.91`                          |
| **User**      | `ubuntu`                                  |
| **SSH Key**   | `~/Downloads/ssh-key-2026-06-02.key`      |
| **Bot Folder**| `~/linkedin-premium-bot`                  |
| **Bot File**  | `bot.py`                                  |
| **Process**   | Managed by PM2 as `linkedin-bot`          |

---

## 📦 Deploy Steps (After Any Code Change)

### Step 1 — Push code from local Mac

```bash
cd /Users/suriyaprakash/Zhahi/Project/Linkedinbot
git add .
git commit -m "your commit message"
git push
```

### Step 2 — Pull & restart on server (single command)

```bash
ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91 "cd ~/linkedin-premium-bot && git pull && pm2 restart linkedin-bot"
```

### ✅ That's it! Bot is updated and running.

---

## 🤖 Instructions for AI Agents

If you are an AI agent making code changes to this project, you **MUST** follow these steps after every modification:

1. **Stage & commit** all changed files:
   ```bash
   git add .
   git commit -m "descriptive commit message"
   ```

2. **Push** to GitHub:
   ```bash
   git push
   ```

3. **Deploy** to the production server (single SSH command):
   ```bash
   ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91 "cd ~/linkedin-premium-bot && git pull && pm2 restart linkedin-bot"
   ```

4. **Verify** the bot is online — the PM2 output should show `status: online`.

> ⚠️ **Never skip deployment.** The bot must run 24/7 on the server regardless of whether the user's Mac is on or off.

---

## 🔧 PM2 Commands (run on server via SSH)

```bash
# Check bot status
ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91 "pm2 status"

# View last 50 lines of logs
ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91 "pm2 logs linkedin-bot --lines 50"

# Restart bot
ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91 "pm2 restart linkedin-bot"

# Stop bot
ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91 "pm2 stop linkedin-bot"

# Start bot
ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91 "pm2 start linkedin-bot"
```

---

## 🔑 SSH Shortcut (optional, one-time setup)

```bash
echo 'alias tgbot="ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.200.91"' >> ~/.zshrc
source ~/.zshrc
```
Then just type `tgbot` to connect to the server.

---

## ⚠️ Important Notes

- 🔒 **Don't delete** the SSH key file from `~/Downloads/`
- ✅ Bot **auto-starts** if the server reboots (PM2 handles this)
- ✅ Bot runs **24/7** even when your Mac is off
- 📁 Working directory: `/Users/suriyaprakash/Zhahi/Project/Linkedinbot`
