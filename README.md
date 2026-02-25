# 📅 NovaTasks AI: Google Tasks Assistant (Telegram Bot Edition)

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0?logo=telegram&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-Agent-blueviolet?logo=langchain&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Gemini%202.5%20Flash-8E75B2?logo=google&logoColor=white)
![Google Tasks](https://img.shields.io/badge/Google%20Tasks-API-4285F4?logo=google&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-success)

## 📌 Overview
**NovaTasks AI** is a conversational Virtual Assistant built to manage your Google Tasks directly from Telegram.

Powered by a **LangChain Tool-Calling Agent**, **Google Gemini 2.5 Flash**, and the official **Google Tasks Toolkit**, this bot operates on an **Ephemeral (RAM-based) Memory** architecture. It intelligently holds the context of your conversation just long enough to gather missing task details, then automatically destroys the memory after the task is executed. This ensures natural, multi-turn conversations while aggressively saving API tokens and preventing AI hallucinations.

## ⚠️ IMPORTANT: Why This Bot Is Locked To A Single User?
> This bot is authenticated using your personal Google Workspace credentials. If it were open to the public, anyone on Telegram could read your private to-do lists, add fake tasks, or delete your data!
>
> To prevent this massive security risk, the bot is strictly locked to YOU (the developer). By matching the user's ID with the `TELEGRAM_DEVELOPER_CHAT_ID` stored in your environment variables, the system ensures that only your specific Telegram account can give commands or read your Google Tasks. 
>
> If any stranger attempts to chat with the bot, it will instantly block them and send an intrusion alert directly to your DM.

## ✨ Key Features
### 🧠 Tool-Calling Agent Architecture
Using `create_tool_calling_agent` and the native Google Tasks Toolkit, the system navigates a strict Standard Operating Procedure (SOP) to securely Create, Read, Update, Complete, Un-complete (Reopen), and Delete your tasks.

### 💾 Ephemeral Conversational Memory (Slot-Filling)
Equipped with `ChatMessageHistory` stored securely in the server's RAM, NovaTasks remembers your ongoing conversation. You can give instructions piece by piece (e.g., "Remind me to buy coffee" -> *Bot asks when* -> "Tomorrow morning"). 

### 💥 Auto-Destruct Mechanism
Once a Google Tasks operation is successfully executed, the LLM emits a hidden `[TASK_DONE]` signal. The system intercepts this signal and instantly purges the user's temporary RAM session. This prevents contextual drift, saves massive amounts of LLM tokens, and readies the agent for a completely fresh task.

### 🛡️ Private Security Bouncer
The bot is hard-locked to a specific `TELEGRAM_DEVELOPER_CHAT_ID`. Any unauthorized attempts to interact with the bot are immediately blocked, logged, and silently reported to the developer's DM.

### 🛡️ Markdown Crash Protection
Features a robust double-defense messaging system. If the LLM generates unclosed Markdown symbols (which typically crash Telegram bots), the system automatically intercepts the error, cleans the text, and safely delivers the response as plain text.

## 🛠️ Tech Stack
* **LLM:** Google Gemini 2.5 Flash (via `ChatGoogleGenerativeAI`).
* **Bot Framework:** `python-telegram-bot`
* **Orchestration:** LangChain (Tool-Calling Agent).
* **Memory Backend:** In-Memory Python Dictionary (`ChatMessageHistory`).
* **Task Integration:** Google Tasks API (`google-api-python-client` & `TasksToolkit`).

## 📦 Installation & Deployment

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/viochris/NovaTasks-AI-Telegram.git
    cd NovaTasks-AI-Telegram
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Local Environment Setup (`.env`)**
    Create a `.env` file for local testing:
    ```env
    TELEGRAM_TOKEN_Nova_Tasks=your_telegram_bot_token
    TELEGRAM_CHAT_ID=your_personal_telegram_id
    GOOGLE_API_KEY=your_gemini_api_key
    ```
    *Note: You must also have your `credentials.json` and `token.json` (with Google Tasks API scopes enabled) in the root directory.*

4.  **Run Locally**
    ```bash
    python NovaTasks-AI.py
    ```

### 🖥️ Expected Terminal Output
You will see the bot initialize the LangChain Agent and start polling in real-time:
```text
2026-02-25 10:30:15,123 - root - INFO - 🚀 NovaTasks AI Telegram Bot is currently online and listening...
2026-02-25 10:35:10,001 - httpx - INFO - HTTP Request: POST [https://api.telegram.org/bot1234...:98.../getUpdates](https://api.telegram.org/bot1234...:98.../getUpdates) "HTTP/1.1 200 OK"
2026-02-25 10:40:45,432 - root - WARNING - 🚨 INTRUSION ATTEMPT: Unauthorized access blocked from User ID: 9876...
2026-02-25 10:45:12,000 - root - INFO - 💥 MEMORY RESET: Ephemeral slot for User ID 1234 successfully destroyed!

```

### 🚀 Cloud Deployment (Railway)
This script is designed to be **Always On** via continuous polling. We highly recommend **Railway (PaaS)** for seamless GitHub integration and Docker deployment.

**Strict Instructions for Railway Deployment:** Do **NOT** upload your physical `credentials.json` or `token.json` files to your GitHub repository for security reasons! 
Because this script includes a **Dynamic Credential Generator**, you just need to paste the raw JSON text directly into your Railway Environment Variables. The server will automatically construct the physical files upon startup.

Add these exact keys in your Railway project variables:
* `GOOGLE_CREDENTIALS`: Paste the raw JSON content of your `credentials.json` file.
* `GOOGLE_TOKEN`: Paste the raw JSON content of your `token.json` file.
* `TELEGRAM_TOKEN_Nova_Tasks`: Your Telegram bot token.
* `TELEGRAM_CHAT_ID`: Your exact developer Telegram User ID.
* `GOOGLE_API_KEY`: Your Google Gemini API Key.

## 🚀 Usage Guide
Once the bot is running, start a chat on Telegram:
* `/start` - Initializes the bot and shows the welcome guidelines.
* **Natural Multi-Turn Chat:** Talk directly to perform actions piece by piece.
  * *You:* "Remind me to call the client."
  * *Bot:* "Sure, when do you want to be reminded?"
  * *You:* "Tomorrow at 10 AM."
* **Direct Actions:**
  * "What are my tasks for today?"
  * "I finished writing the report, check it off."
  * "Cancel the grocery shopping task."

---

**Authors:** Silvio Christian, Joe
*"Automate your to-do list. Experience intelligent task management."*
