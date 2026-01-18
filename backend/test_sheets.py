import gspread
import os

CREDENTIALS_FILE = "service_account.json"
SPREADSHEET_NAME = "NewVegasEvents"

print(f"Checking for {CREDENTIALS_FILE}...")
if not os.path.exists(CREDENTIALS_FILE):
    print("ERROR: service_account.json NOT found!")
    exit(1)
print("File found.")

try:
    print("Attempting to authenticate...")
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    print("Authentication successful.")
    
    print(f"Attempting to open spreadsheet: '{SPREADSHEET_NAME}'...")
    sh = gc.open(SPREADSHEET_NAME)
    print("Spreadsheet opened successfully!")
    
    print(f"Opening first worksheet...")
    worksheet = sh.sheet1
    data = worksheet.get_all_records()
    print(f"Success! Found {len(data)} rows.")
    print("First row data:", data[0] if data else "No data")

except gspread.exceptions.SpreadsheetNotFound:
    print(f"\nERROR: Spreadsheet '{SPREADSHEET_NAME}' NOT FOUND.")
    print("Possible reasons:")
    print("1. You named the sheet incorrectly in Google Drive.")
    print("2. You haven't shared it with the service account email.")
    
    # Try to print the email to help the user
    try:
        import json
        with open(CREDENTIALS_FILE) as f:
            creds = json.load(f)
            print(f"\nPlease share the sheet with this email: {creds.get('client_email')}")
    except:
        pass

except Exception as e:
    print(f"\nERROR: {e}")
