from openai import OpenAI
import httpx

# עדכן את הכתובת החדשה שתקבל מ-Ngrok אחרי שתריץ אותו על פורט 8000
TUNNEL_URL = "https://ransack-gently-stencil.ngrok-free.dev/v1"

print(f"Testing direct connection to: {TUNNEL_URL} ...\n")

try:
    # פתרון קריטי: הזרקת כותרת שעוקפת את מסך האזהרה של Ngrok
    custom_http_client = httpx.Client(
        headers={"ngrok-skip-browser-warning": "true"}
    )

    # מתחברים ל-vLLM שלנו
    client = OpenAI(
        base_url=TUNNEL_URL,
        api_key="no-key-required",
        http_client=custom_http_client # שימוש בלקוח המותאם
    )

    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct", # חייב להיות בדיוק השם שרץ ב-vLLM
        messages=[
            {"role": "user", "content": "היי! תענה לי בעברית בבקשה: האם אתה מקבל אותי דרך המנהרה?"}
        ],
        max_tokens=50,
        temperature=0.7
    )

    print("✅ SUCCESS! Qwen received the message and replied:")
    print("======================================================")
    print(response.choices[0].message.content)
    print("======================================================")

except Exception as e:
    print("❌ FAILED to connect or get response:")
    print(e)