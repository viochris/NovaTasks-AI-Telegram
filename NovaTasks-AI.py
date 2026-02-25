import os
import logging
from datetime import datetime, timedelta, timezone

# --- Third-Party Libraries ---
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- LangChain & Generative AI Libraries ---
from langchain_google_community import TasksToolkit
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory

# ==========================================
# ENVIRONMENT VARIABLES & CONFIGURATION
# ==========================================
# Load sensitive credentials from the local .env file securely
load_dotenv()

# Fetch configuration keys from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_Nova_Tasks")
TELEGRAM_DEVELOPER_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ==========================================
# DYNAMIC CREDENTIAL GENERATOR FOR CLOUD DEPLOYMENT (RAILWAY)
# ==========================================
# LangChain's CalendarToolkit strictly requires physical 'credentials.json' and 'token.json' files to function.
# When running locally, these files already exist in your folder, so this code will safely skip execution.
# However, during cloud deployment (like on Railway), these files are typically ignored via .gitignore for security.
# This script dynamically generates the required physical files on the server upon startup by pulling the raw JSON data from Railway's Environment Variables.

# 1. Generate 'credentials.json' on the server if it doesn't exist
creds_env = os.getenv("GOOGLE_CREDENTIALS")
if creds_env and not os.path.exists("credentials.json"):
    with open("credentials.json", "w") as f:
        f.write(creds_env)

# 2. Generate 'token.json' on the server if it doesn't exist
token_env = os.getenv("GOOGLE_TOKEN")
if token_env and not os.path.exists("token.json"):
    with open("token.json", "w") as f:
        f.write(token_env)

# ==========================================
# SYSTEM LOGGING SETUP
# ==========================================
# Configure basic logging to monitor bot activity, track routing, and capture errors in the terminal
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================================
# IN-MEMORY CONVERSATIONAL MANAGER (SLOT-FILLING)
# ==========================================
# 1. Initialize the global ephemeral store (RAM dictionary).
# MUST BE OUTSIDE the function so it persists across multiple chat messages
# until we explicitly destroy it after the task is done.
ephemeral_store = {}

def get_session_history(session_id: str):
    """
    Retrieves or initializes an in-memory chat history for a specific user session.
    
    This function acts as a temporary 'Slot-Filling' buffer. It stores the 
    conversational context purely in the server's RAM (not SQL database) based 
    on the unique Telegram User ID. Once the AI successfully executes a Calendar 
    tool, this specific session's memory will be purged/destroyed to save tokens 
    and prevent contextual hallucinations.
    
    Args:
        session_id (str): The unique identifier for the user (Telegram User ID).
        
    Returns:
        ChatMessageHistory: The ephemeral LangChain memory instance for the current session.
    """
    # 2. Check if the user already has an active "shopping cart" (memory buffer)
    if session_id not in ephemeral_store:
        # If not, create a fresh, empty memory instance for them
        ephemeral_store[session_id] = ChatMessageHistory()

    # 3. Return the user's specific memory buffer to the AI Agent
    return ephemeral_store[session_id]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    welcome_text = (
        "👋 **Hey there! I'm NovaTasks.**\n\n"
        "I'm your Google Tasks assistant right here on Telegram. "
        "No need to use strict commands—just chat with me naturally and I'll keep your to-dos organized!\n\n"
        "**Here are a few things you can ask me to do:**\n"
        "✨ *Add a task:* \"Remind me to buy coffee tomorrow morning.\"\n"
        "📋 *Check your list:* \"What do I have to do today?\"\n"
        "✅ *Check things off:* \"I finished the weekly report, mark it as done.\"\n"
        "🗑️ *Delete a task:* \"Cancel the gym task for tonight.\"\n\n"
        "What's on your mind today?"
    )

    await context.bot.send_message(
        chat_id=chat_id, 
        text=welcome_text,
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processes standard text messages sent by the user to the bot.
    
    This handler acts as the core conversational engine. It captures the user's input, 
    forwards it to the Google Gemini LLM for processing, and seamlessly transmits 
    the generated response back to the Telegram chat.
    
    Args:
        update (telegram.Update): The payload containing incoming message details.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The context object for API interactions.
    """

    # 1. Extract metadata and user input from the incoming Telegram update
    user_text = update.message.text
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # --- SECURITY BOUNCER ---
    # Strictly limit access to the designated developer to protect calendar privacy
    if str(user_id) != str(TELEGRAM_DEVELOPER_CHAT_ID):
        # Log the intrusion attempt to the terminal so the developer knows who tried to snoop
        logging.warning(f"🚨 INTRUSION ATTEMPT: Unauthorized access blocked from User ID: {user_id} (Name: {user_name})")

        # 1. Attempt to send a warning to the intruder and kick them out
        try:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="🚨 **Access Denied!** Unauthorized user detected. I am exclusively configured to assist my designated developer.",
                parse_mode="Markdown"
            )
        except Exception as e:
            # Catch errors if the user blocks the bot immediately before receiving the warning
            logging.error(f"Failed to send Access Denied message to intruder (User ID: {user_id}): {e}")

        # 2. Attempt to send a silent security alert to the Developer's DM
        try:
            alert_msg = (
                f"⚠️ **SECURITY ALERT** ⚠️\n\n"
                f"Someone tried to access your Calendar Bot!\n"
                f"👤 **Name:** {user_name}\n"
                f"🆔 **User ID:** `{user_id}`\n"
                f"💬 **They typed:** _{user_text}_"
            )
            await context.bot.send_message(
                chat_id=TELEGRAM_DEVELOPER_CHAT_ID,
                text=alert_msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            # Catch errors if the developer's chat ID is invalid or the bot cannot message them
            logging.error(f"Failed to send security alert to Developer: {e}")
            
        # 3. Terminate the function immediately to prevent unauthorized calendar access
        return

    try: 
        # 1. Trigger the 'Typing...' action indicator in the Telegram UI
        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

        # 2. Initialize the Google Calendar Toolkit
        toolkit = TasksToolkit()
        tools = toolkit.get_tools()

        # 3. Capture the Exact Current System Time for Contextual Accuracy
        wib_timezone = timezone(timedelta(hours=7))
        current_datetime = datetime.now(wib_timezone).strftime("%Y-%m-%d %H:%M:%S WIB")
        
        # 4. Construct the Custom Hybrid Tool-Calling Prompt for GOOGLE TASKS
        # This serves as the core "Brain" of the agent, defining strict Standard Operating Procedures (SOP).
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are an elite, highly capable Personal Assistant managing the user's Google Tasks.
            CURRENT SYSTEM TIME: {current_datetime}
            
            CRITICAL RULES:
            1. TASKLIST ID: Whenever a tool requires a 'tasklist' or 'tasklist_id', ALWAYS use exactly the string '@default' (which targets the user's main task list) unless the user specifies a different list.
            2. TIME CONTEXT & CALCULATION: 
               - Base all date calculations strictly on the CURRENT SYSTEM TIME provided above.
               - "Today" is {current_datetime[:10]}.
               - "Tomorrow", "Next week", "Yesterday", or "In 3 days" must be calculated relative to today's date.
               - Example: If today is Wednesday, "Day after tomorrow" is Friday.
               - Google Tasks due dates typically require RFC3339 format (e.g., YYYY-MM-DDTHH:MM:SSZ).
            3. LANGUAGE & FORMATTING (CRITICAL): 
               - Always respond naturally in the EXACT SAME language the user typed.
               - ABSOLUTELY NO MARKDOWN: You MUST output strictly in PLAIN TEXT.
               - DO NOT use any formatting symbols (NO asterisks *, NO underscores _, NO backticks `, NO bold, NO italics). 
               - Telegram will crash if you use these symbols. Use standard punctuation only. Use hyphens (-) for lists or separators.
            4. CONVERSATIONAL MEMORY: You have access to the user's previous messages in 'chat_history'. ALWAYS check this history first to find missing details. DO NOT ask the user for information they have already provided.
            5. PARAMETER SAFETY (MANDATORY DEADLINE CHECK):
                - If the user asks to create a task or reminder, BUT does not provide a specific time or date, you MUST STOP and ask them: "Untuk kapan?" (For when?).
                - DO NOT create the task until the user provides a deadline, OR until the user explicitly says "Tidak usah pakai waktu" (No deadline).
                - Never invent tasks or due dates yourself.
            6. THE SNIPER RULE: To Delete, Update, or Complete a task, you MUST possess the exact 'task_id'. If you do not have it, you MUST use the task-listing tool first to find it.
            7. AUTO-DESTRUCT SIGNAL: If you SUCCESSFULLY use a tool to create, update, delete, or complete a task, you MUST include the exact string "[TASK_DONE]" at the very end of your final response to the user.
            
            STANDARD OPERATING PROCEDURES (SOP) FOR GOOGLE TASKS ACTIONS:
            
            A. CREATING A TASK (Trigger words: "Add task", "Remind me", "Ingetin", "Tolong catat", "Jangan lupa"):
            - Step 1: Check if the user has provided a due date or time.
            - Step 2: IF MISSING, ask the user for the time/date.
            - Step 3: Once you have the title and the due date, use the tool designed for inserting/creating a task.
            
            B. READING / CHECKING TASKS (e.g., "What are my tasks today?"):
            - Use the tool designed for listing tasks. 
            - Summarize the retrieved tasks naturally, mentioning their due dates or notes if any.
            
            C. COMPLETING A TASK (e.g., "Check off the meeting", "I finished buying milk"):
            - Step 1: Use the task-listing tool to find the specific task and extract its 'task_id'.
            - Step 2: Use the task-updating tool with that 'task_id' and set the status to 'completed'.

            D. UN-COMPLETING / REOPENING A TASK (e.g., "Mark the meeting as not done", "Uncheck buying milk"):
            - Step 1: Use the task-listing tool to find the specific task and extract its 'task_id'.
            - Step 2: Use the task-updating tool with that 'task_id' and set the status to 'needsAction'.
            
            E. EDITING / UPDATING A TASK:
            - Step 1: Use the task-listing tool to extract the exact 'task_id'.
            - Step 2: Use the task-updating tool using that 'task_id' along with the new details.
            
            F. DELETING A TASK:
            - Step 1: Use the task-listing tool to extract the exact 'task_id'.
            - Step 2: Use the tool designed for deleting a task using that 'task_id'.
            """),
            
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 5. Initialize the LLM Engine
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.3
        )

        # 6. Bind the Reasoning Engine (The Brain)
        agent_brain = create_tool_calling_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )

        # 7. Initialize the Base Runtime Executor (The Body)
        agent_executor = AgentExecutor(
            agent=agent_brain,
            tools=tools,
            handle_parsing_errors=True
        )

        # Retrieve ephemeral memory buffer
        memory_buffer = get_session_history(str(user_id))

        # 9. Execute the Agent workflow using the User's unique session ID
        response = agent_executor.invoke({
            "input": user_text,
            "chat_history": memory_buffer.messages
        })

        # 10. Safely parse the LLM's output
        if "output" in response and len(response["output"]) > 0:
            final_answer = response.get("output", "Sorry, I am unable to process that scheduling request right now.")

            # Sanitize the output if the LLM returns a complex list structure
            if isinstance(final_answer, list):
                cleaned_text = ""
                for part in final_answer:
                    if isinstance(part, dict) and "text" in part:
                        cleaned_text += part["text"]
                    elif isinstance(part, str):
                        cleaned_text += part
                final_answer = cleaned_text   
        else:
            final_answer = "Sorry, I am unable to process that scheduling request right now."
        
        memory_buffer.add_user_message(user_text)
        memory_buffer.add_ai_message(final_answer)

        # 11. THE MAGIC: AUTO-DESTRUCT MEMORY (SLOT RESET) 💥
        # If the AI signals that the CRUD calendar task is completed, we purge the RAM memory.
        # This prevents contextual drift, saves API tokens, and resets the agent for a fresh task.
        if "[TASK_DONE]" in final_answer:
            # Strip the secret trigger word from the final output so the user never sees it
            final_answer = final_answer.replace("[TASK_DONE]", "").strip()
            
            # Destroy the user's temporary memory session
            ephemeral_store.pop(str(user_id), None)
            logging.info(f"💥 MEMORY RESET: Ephemeral slot for User ID {user_id} successfully destroyed!")

        # 12. Handle Telegram's Message Length Limits
        # Telegram strict limit is 4096. We use 4000 as a safety buffer.
        MAX_LENGTH = 4000
        message_to_send = []

        # Check if the final response exceeds the maximum length constraint
        if len(final_answer) <= MAX_LENGTH:
            message_to_send.append(final_answer)
        else:
            logging.info("⚠️ Message is too long. Splitting into readable chunks...")

            # Split by double newlines to preserve Markdown paragraph structure
            parts = final_answer.split('\n\n')
            current_chunks = ""

            for part in parts:
                # Check if adding the next part exceeds the limit
                if len(current_chunks) + len(part) + 2 < MAX_LENGTH:
                    current_chunks += part + "\n\n"
                else:
                    # If the chunk is full, append to list and start a new one
                    if current_chunks.strip():
                        message_to_send.append(current_chunks)
                    current_chunks = part + "\n\n"

            # Append any remaining text in the buffer
            if current_chunks.strip():
                message_to_send.append(current_chunks)

        # 13. Transmit the formulated chunks back to the user asynchronously
        for i, answer in enumerate(message_to_send):
            await context.bot.send_message(
                chat_id=chat_id,
                text=answer,
                parse_mode="Markdown"
            )
    
    except Exception as e:
        # 14. Prevent silent failures by safely catching, categorizing, and notifying the user
        error_msg = str(e).lower()
        logging.error(f"Failed to generate AI response for User {user_id} ({user_name}): {e}")
        
        # Scenario A: AI Rate Limits or Exhausted Quota (Gemini API)
        if "quota" in error_msg or "429" in error_msg or "exhausted" in error_msg:
            reply_text = "⚠️ **API Limit Reached:** My AI engine is receiving too many requests right now or has reached its daily capacity. Please try again later or tomorrow!"
            
        # Scenario B: Authentication or Billing Issues (Missing/Invalid API Key)
        elif "api_key" in error_msg or "key invalid" in error_msg or "403" in error_msg:
            reply_text = "🛑 **Configuration Error:** My API key seems to be invalid or expired. Please check the system environment settings."
            
        # Scenario C: Google Calendar Access Issues (Token expired or Calendar not found)
        elif "unauthorized" in error_msg or "invalid_grant" in error_msg or "calendar_id" in error_msg:
            reply_text = "📅 **Calendar Sync Error:** I am having trouble accessing your Google Calendar. The authorization token might be expired or the calendar ID is incorrect."
            
        # Scenario D: The Fallback (Catch-all for network drops, timeouts, or unknown bugs)
        else:
            reply_text = "⚠️ **System Error:** My AI engine is currently unreachable or encountering an unexpected issue. Please try again in a moment!"

        # Safely transmit the categorized error message back to the user
        try:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=reply_text, 
                parse_mode="Markdown"
            )
        except Exception as send_error:
            # The absolute last line of defense in case Telegram itself is down
            logging.error(f"CRITICAL: Failed to even send the error message to user! {send_error}")
            
# ==========================================
# GLOBAL ERROR HANDLING
# ==========================================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler for the Telegram bot routing system.
    
    This function acts as the ultimate safety net ("Ambulance"). If any handler 
    encounters an unhandled exception, it logs the error to the terminal and 
    sends a direct emergency message to the developer's Telegram chat.
    
    Args:
        update (telegram.Update): The incoming update that caused the error.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The context containing the error object.
    """
    
    # 1. Log the critical error to the system console for debugging
    logging.error(f"Exception while handling an update: {context.error}")

    # 2. Construct the emergency notification payload
    error_message = (
        f"🚨 **SYSTEM ALERT: BOT ENCOUNTERED AN ERROR!** 🚨\n\n"
        f"**Error Details:**\n`{context.error}`"
    )
    
    # 3. Attempt to alert the developer via Telegram DM
    try:
        # Utilize the TELEGRAM_DEVELOPER_CHAT_ID defined in the .env variables
        await context.bot.send_message(
            chat_id=TELEGRAM_DEVELOPER_CHAT_ID, 
            text=error_message, 
            parse_mode="Markdown"
        )
    except Exception as e:
        # Gracefully handle the scenario where the error alert fails to deliver 
        # (e.g., if the developer blocked the bot or the chat ID is invalid)
        logging.error(f"Failed to deliver error alert to Developer: {e}")
        pass

# ==========================================
# MAIN APPLICATION EXECUTOR
# ==========================================
if __name__ == "__main__":
    # 1. Initialize and build the Telegram Bot Application using the secure environment token
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 2. Register Core Command Handlers (/start)
    app.add_handler(CommandHandler("start", start_command))
    
    # 3. Register the Conversational Message Handler 
    # This captures all regular text prompts intended for the AI while explicitly bypassing commands
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # 4. Register the Global Error Handler (The Ambulance) to safely catch and log unexpected system crashes
    app.add_error_handler(error_handler)

    # 5. Ignite the AI engine and start continuous polling for incoming Telegram updates
    logging.info("🚀 NovaCal AI Telegram Bot is currently online and listening...")
    app.run_polling()