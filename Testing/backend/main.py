import os
import asyncio
import json
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI

app = FastAPI(title="AI-Rescue Connect Backend")

# Initialize OpenAI client to connect to local Ollama (or vLLM in the cloud)
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2:0.5b")

client = AsyncOpenAI(
    base_url=LLM_API_URL,
    api_key="ollama-local"
)

# Concurrency lock to prevent VRAM overload (ADR-006)
gpu_semaphore = asyncio.Semaphore(1)

class WebhookPayload(BaseModel):
    sender: str
    message: str

# --- Mock Database ---
MOCK_VOLUNTEERS = [
    {"id": "v1", "name": "Yossi", "skills": ["Medic", "First Aid"], "distance_km": 1.2, "status": "On-Duty"},
    {"id": "v2", "name": "Ronit", "skills": ["Firefighter", "Search & Rescue"], "distance_km": 0.5, "status": "On-Duty"},
    {"id": "v3", "name": "David", "skills": ["General Volunteer", "Driving"], "distance_km": 0.3, "status": "On-Duty"},
    {"id": "v4", "name": "Sarah", "skills": ["Medic"], "distance_km": 1.2, "status": "Off-Duty"}
]

async def llm_inference(messages, require_json=False):
    """Helper function to call the LLM safely behind the semaphore lock."""
    async with gpu_semaphore:
        kwargs = {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0.0
        }
        if require_json:
            kwargs["response_format"] = {"type": "json_object"}
            
        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM Error: {e}")
            return None

async def process_emergency_chain(sender: str, message: str):
    print(f"\n[{sender}] ===============================================")
    print(f"[{sender}] STARTING PROMPT CHAIN FOR: '{message}'")
    
    # ---------------------------------------------------------
    # PROMPT A: Extraction (JSON)
    # ---------------------------------------------------------
    print(f"\n[{sender}] Step 1: Extracting Location and Severity...")
    sys_prompt_a = '''You are a highly analytical emergency dispatcher AI. 
Your objective is to extract the location, severity, and incident type from the citizen's message.
You MUST respond ONLY with a valid JSON object. Do not include any conversational text outside the JSON.

Rules:
1. "reasoning": Briefly analyze the text. Identify the emergency type, assess severity, and differentiate the actual incident location from the user's current location if they fled.
2. "location": Extract the exact street and city of the incident. If no location is provided, set all nested fields to null.
3. "severity": Must be strictly one of: ["Low", "Medium", "High", "Critical", "Unknown"].
4. "incident_type": Describe the emergency (e.g., "Fire", "Medical", "Car Crash"). If non-emergency, output "Non-Emergency".

JSON Structure:
{
  "reasoning": "thought process goes here",
  "location": {
    "street": "extracted street or null",
    "city": "extracted city or null",
    "raw_text": "exact text used for location or null"
  },
  "severity": "High",
  "incident_type": "Fire"
}'''
    
    res_a = await llm_inference([
        {"role": "system", "content": sys_prompt_a},
        {"role": "user", "content": message}
    ], require_json=True)
    
    if not res_a:
        print(f"[{sender}] Chain failed at Step 1.")
        return
        
    print(f"[{sender}] Step 1 Result:\n{res_a}")
    
    try:
        extracted_data = json.loads(res_a)
    except Exception:
        print(f"[{sender}] Failed to parse JSON from Step 1. Aborting.")
        return
        
    incident_type = extracted_data.get("incident_type", "Unknown")
    
    # EARLY EXIT 1: Non-Emergency
    if incident_type == "Non-Emergency":
        print(f"[{sender}] Non-Emergency detected. Sending standard template.")
        print(f"\n[{sender}] Final SMS:\n======================================================\nThis line is for emergencies only. Please contact standard services.\n======================================================")
        return
        
    # EARLY EXIT 2: Missing Location
    loc = extracted_data.get("location", {})
    if loc is None or (loc.get("street") is None and loc.get("city") is None and loc.get("raw_text") is None):
        print(f"[{sender}] Location Missing! Skipping dispatch.")
        print(f"\n[{sender}] Final SMS:\n======================================================\nWe are here to help. Where are you located? Please send your exact address.\n======================================================")
        return

    # ---------------------------------------------------------
    # PROMPT B: Volunteer Selection (JSON)
    # ---------------------------------------------------------
    print(f"\n[{sender}] Step 2: Selecting best volunteer...")
    
    # FILTER: Remove off-duty volunteers before sending to LLM
    available_volunteers = [v for v in MOCK_VOLUNTEERS if v.get("status") != "Off-Duty"]
    
    sys_prompt_b = f'''You are a strategic AI dispatcher logic unit. 
You are provided with an incident type, severity, and a JSON list of the top available on-duty volunteers closest to the scene.

Your goal is to select the BEST volunteer ID based on these priorities:
1. Skill Match: Ensure the volunteer's skills match the incident (e.g., Medical for injuries, Firefighting for fires). 
2. Distance: Pick the closest qualified volunteer.
3. Tie-breaker: If distance and skills are identical, pick the one with better availability stats.

You MUST respond ONLY with a valid JSON object. 

JSON Structure:
{{
  "reason": "Explain your step-by-step evaluation of the provided candidates, comparing their skills and distances.",
  "selected_volunteer_id": "v1" 
}}'''

    user_prompt_b = f"Incident type: {incident_type}\nSeverity: {extracted_data.get('severity')}\nAvailable Volunteers:\n{json.dumps(available_volunteers, indent=2)}\n\nSelect the best volunteer ID."

    res_b = await llm_inference([
        {"role": "system", "content": sys_prompt_b},
        {"role": "user", "content": user_prompt_b}
    ], require_json=True)
    
    print(f"[{sender}] Step 2 Result:\n{res_b}")
    
    try:
        selection_data = json.loads(res_b)
        selected_id = selection_data.get("selected_volunteer_id")
    except Exception:
        selected_id = None
        
    # Find the actual volunteer object
    selected_volunteer = next((v for v in available_volunteers if v["id"] == selected_id), None)

    # ---------------------------------------------------------
    # PROMPT C: Calming Response Generation (Text)
    # ---------------------------------------------------------
    print(f"\n[{sender}] Step 3: Generating SMS response...")
    
    if selected_volunteer is None:
        print(f"[{sender}] No qualified volunteer found (selected_volunteer_id was null).")
        sys_prompt_c = f'''You are an empathetic emergency dispatcher. 
A citizen reported an emergency: "{message}"
We could not find a qualified local volunteer for this specific emergency.

Task: Write a very short, calming response to the citizen IN ENGLISH.
Tell them that official emergency services (101/102) have been alerted and are on the way. Give ONE safety instruction.
DO NOT use markdown. DO NOT include filler text. Output ONLY the raw SMS.'''
        
        user_prompt_c = "Write the SMS message to the citizen."

    else:
        sys_prompt_c = f'''You are an empathetic emergency dispatcher. 
A citizen reported an emergency. We have dispatched a volunteer to their location.

Task: Write a very short, calming response to the citizen IN ENGLISH.
1. Confirm that help is on the way.
2. Mention the volunteer's name and distance.
3. Give ONE quick safety instruction.

STRICT RULES:
- DO NOT use markdown.
- DO NOT include conversational filler, greetings, or explanations. 
- Output ONLY the raw SMS text.

Few-Shot Examples:

Input Context:
- User Message: "My kitchen is on fire!"
- Dispatched Volunteer: David
- Volunteer Skills: Firefighter
- ETA / Distance: 0.5km
Output:
Help is on the way. David is 0.5km away and arriving soon. Please wait outside the building safely.

Input Context:
- User Message: "Someone stabbed a guy on the street, he is bleeding."
- Dispatched Volunteer: Ronit
- Volunteer Skills: Medic
- ETA / Distance: 2km
Output:
We received your report. Medic Ronit is 2km away and en route. Apply direct pressure to the wound with a clean cloth.

Input Context:
- User Message: "{message}"
- Dispatched Volunteer: {selected_volunteer['name']}
- Volunteer Skills: {", ".join(selected_volunteer['skills'])}
- ETA / Distance: {selected_volunteer['distance_km']}km
Output:'''
        
        user_prompt_c = "Generate the SMS output."

    res_c = await llm_inference([
        {"role": "system", "content": sys_prompt_c},
        {"role": "user", "content": user_prompt_c}
    ], require_json=False)
    
    print(f"\n[{sender}] Step 3 Result (Final SMS to user):\n======================================================\n{res_c}\n======================================================")
    

@app.post("/api/v1/webhook")
async def handle_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    print(f"FastAPI: Received webhook from {payload.sender}. Sending 200 OK immediately and delegating to background task.")
    
    background_tasks.add_task(process_emergency_chain, payload.sender, payload.message)
    
    return {
        "status": "received",
        "message": "Webhook acknowledged. Processing in background."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8050, reload=True)
