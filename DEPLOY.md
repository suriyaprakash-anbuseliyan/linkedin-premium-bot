# 🚀 Deployment Guide — LinkedIn Premium Bot

> **Rule:** After EVERY code change, you MUST deploy to the server.  
> The bot runs 24/7 on the Oracle Cloud server — not on your local Mac.

---

## 🖥️ Server Info

| Detail        | Value                                      |
|---------------|-------------------------------------------|
| **IP**        | `140.245.242.47`                          |
| **User**      | `ubuntu`                                  |
| **SSH Key**   | `sshkey/ssh-key-2026-08-01.key` (or `~/Downloads/ssh-key-2026-08-01.key`) |
| **Bot Folder**| `~/bot`                                   |
| **Bot File**  | `bot.py`                                  |
| **Service**   | Managed by systemd as `tgbot.service`     |

---

## 📦 Deploy Steps (After Any Code Change)

### Step 1 — Push code to GitHub

```bash
git add .
git commit -m "your commit message"
git push
```

### Step 2 — Sync files to server & restart

```bash
# Sync files to server
rsync -avz -e "ssh -i sshkey/ssh-key-2026-08-01.key" --exclude '.git' --exclude 'venv' --exclude '__pycache__' --exclude '.DS_Store' ./ ubuntu@140.245.242.47:~/bot/

# Restart systemd service on server
ssh -i sshkey/ssh-key-2026-08-01.key ubuntu@140.245.242.47 "sudo systemctl restart tgbot"
```

### ✅ That's it! Bot is updated and running.

---

## 🔧 Service Commands (run on server via SSH)

```bash
# Check bot status
ssh -i sshkey/ssh-key-2026-08-01.key ubuntu@140.245.242.47 "sudo systemctl status tgbot"

# View recent logs
ssh -i sshkey/ssh-key-2026-08-01.key ubuntu@140.245.242.47 "sudo journalctl -u tgbot -n 50 --no-pager"

# Restart bot
ssh -i sshkey/ssh-key-2026-08-01.key ubuntu@140.245.242.47 "sudo systemctl restart tgbot"
```

---

## 🔑 SSH Shortcut (optional, one-time setup)

```bash
echo 'alias tgbot="ssh -i ~/Downloads/ssh-key-2026-06-02.key ubuntu@140.245.242.47"' >> ~/.zshrc
source ~/.zshrc
```
Then just type `tgbot` to connect to the server.

---

## ⚠️ Important Notes

- 🔒 **Don't delete** the SSH key file from `~/Downloads/`
- ✅ Bot **auto-starts** if the server reboots (PM2 handles this)
- ✅ Bot runs **24/7** even when your Mac is off
- 📁 Working directory: `/Users/suriyaprakash/Zhahi/Project/Linkedinbot`
