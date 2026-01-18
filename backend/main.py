from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
import gspread
import os
import json

app = FastAPI()

# Mount the static directory
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# --- Google Sheets Setup ---
# We will look for a file named 'service_account.json' in this directory
CREDENTIALS_FILE = "env_vars/service_account.json"
SPREADSHEET_NAME = "NewVegasEvents"

def get_sheet_data():
    """
    Attempts to connect to Google Sheets and fetch events.
    Prioritizes 'GOOGLE_CREDENTIALS_JSON' env var, then falls back to local file.
    """
    try:
        # 1. Try Environment Variable (Best for Render/Production)
        json_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if json_creds:
            creds_dict = json.loads(json_creds)
            gc = gspread.service_account_from_dict(creds_dict)
        
        # 2. Try Local File (Best for Local Dev)
        elif os.path.exists(CREDENTIALS_FILE):
            gc = gspread.service_account(filename=CREDENTIALS_FILE)
        
        else:
            print("No credentials found (Env var or file).")
            return None

        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.sheet1
        # Get all records as a list of dicts
        return worksheet.get_all_records()

    except Exception as e:
        print(f"Error connecting to Google Sheets: {e}")
        return None

# --- Email Configuration ---
class ContactForm(BaseModel):
    name: str
    email: EmailStr
    topic: str
    message: str

def load_mail_config():
    """
    Loads email settings from 'MAIL_CONFIG_JSON' env var if present,
    or falls back to local 'env_vars/mail_config.json' file,
    otherwise falls back to individual environment variables.
    """
    json_config = os.getenv("MAIL_CONFIG_JSON")
    local_config_file = "env_vars/mail_config.json"

    defaults = {
         "MAIL_USERNAME": "your-email@gmail.com",
         "MAIL_PASSWORD": "your-app-password",
         "MAIL_FROM": "your-email@gmail.com",
         "MAIL_PORT": 587,
         "MAIL_SERVER": "smtp.gmail.com",
         "MAIL_RECIPIENT": None 
    }
    
    config = None

    # 1. Try loading from Env Var (Priority)
    if json_config:
        try:
            config = json.loads(json_config)
        except json.JSONDecodeError:
            print("Error parsing MAIL_CONFIG_JSON")

    # 2. Try loading from Local File (if Env Var failed or not set)
    if not config and os.path.exists(local_config_file):
        try:
            with open(local_config_file, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error reading local mail config: {e}")

    # Process config if found
    if config:
        # Ensure port is an integer
        if "MAIL_PORT" in config:
            config["MAIL_PORT"] = int(config["MAIL_PORT"])
        return config

    # 3. Fallback to individual env vars
    return {
        "MAIL_USERNAME": os.getenv("MAIL_USERNAME", defaults["MAIL_USERNAME"]),
        "MAIL_PASSWORD": os.getenv("MAIL_PASSWORD", defaults["MAIL_PASSWORD"]),
        "MAIL_FROM": os.getenv("MAIL_FROM", defaults["MAIL_FROM"]),
        "MAIL_PORT": int(os.getenv("MAIL_PORT", defaults["MAIL_PORT"])),
        "MAIL_SERVER": os.getenv("MAIL_SERVER", defaults["MAIL_SERVER"]),
        "MAIL_RECIPIENT": os.getenv("MAIL_RECIPIENT")
    }

# Load config once at startup
mail_cfg = load_mail_config()

conf = ConnectionConfig(
    MAIL_USERNAME = mail_cfg.get("MAIL_USERNAME"),
    MAIL_PASSWORD = mail_cfg.get("MAIL_PASSWORD"),
    MAIL_FROM = mail_cfg.get("MAIL_FROM"),
    MAIL_PORT = mail_cfg.get("MAIL_PORT"),
    MAIL_SERVER = mail_cfg.get("MAIL_SERVER"),
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

@app.post("/api/contact")
async def send_contact_email(form: ContactForm, background_tasks: BackgroundTasks):
    """
    Receives contact form data and sends an email to the admin.
    """
    message_body = f"""
    New Contact Request from New Vegas Website:
    
    Name: {form.name}
    Email: {form.email}
    Topic: {form.topic}
    
    Message:
    {form.message}
    """

    # Determine recipient (use explicit recipient or fallback to sender)
    recipient = mail_cfg.get("MAIL_RECIPIENT") or mail_cfg.get("MAIL_FROM")

    message = MessageSchema(
        subject=f"New Vegas Contact: {form.topic}",
        recipients=[recipient], 
        body=message_body,
        subtype=MessageType.plain
    )

    fm = FastMail(conf)
    
    try:
        # Send in background to not block the response
        background_tasks.add_task(fm.send_message, message)
        return {"message": "Email sent successfully"}
    except Exception as e:
        print(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")

@app.get("/")
def read_root():
    return FileResponse("../frontend/index.html")

@app.get("/api/events")
def get_events():
    data = get_sheet_data()
    
    if data:
        return data

    # Fallback Data (if sheet connection fails)
    return [
        {"Day": "Czwartki", "Time": "20:00", "Title": "Wielkie Karaoke (Fallback)", "Description": "Najgłośniejsza impreza na dzielni. Wstęp wolny."},
        {"Day": "Wtorki", "Time": "All Day", "Title": "Bilard Night", "Description": "Zniżka na stoły -50% dla studentów."},
        {"Day": "Środy", "Time": "20:30", "Title": "Stand-Up / Open Mic", "Description": "Testy nowych żartów i występy lokalnych komików."},
        {"Day": "Pt / Sob", "Time": "21:00", "Title": "Koncerty Garażowe", "Description": "Sprawdź FB, kto gra w tym tygodniu."}
    ]
