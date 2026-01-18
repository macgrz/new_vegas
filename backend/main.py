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
CREDENTIALS_FILE = "service_account.json"
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

# These env vars must be set in Render for this to work
conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "your-email@gmail.com"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "your-app-password"),
    MAIL_FROM = os.getenv("MAIL_FROM", "your-email@gmail.com"),
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com"),
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

    message = MessageSchema(
        subject=f"New Vegas Contact: {form.topic}",
        recipients=[os.getenv("MAIL_RECIPIENT", os.getenv("MAIL_FROM"))], # Send to self/admin
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
