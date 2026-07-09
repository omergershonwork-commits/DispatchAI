import requests
import json

url = "http://localhost:8050/api/v1/webhook"

payload = {
    "sender": "+972501234567",
    "message": "הצילו! יש שריפה בדירה שלי ברחוב הרצל 10, קומה 3 בתל אביב. אני לא נושם מהעשן ויש פה לכודים!"
}

headers = {
    "Content-Type": "application/json",
    "Bypass-Tunnel-Reminder": "true"
}

print("======================================================")
print(f"Sending test payload to FastAPI webhook:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
print("======================================================")

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"\nResponse status code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    
    print("\n👉 SUCCESS! The server accepted the message immediately (to keep WhatsApp happy).")
    print("👉 NOW LOOK AT THE FASTAPI TERMINAL to watch the AI Prompt Chain running in the background!")
except Exception as e:
    print(f"\nFailed to connect to FastAPI server: {str(e)}")
    print("Make sure you have started the FastAPI server with: python main.py")
