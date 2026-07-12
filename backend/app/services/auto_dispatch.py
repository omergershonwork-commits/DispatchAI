import asyncio
from typing import Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.incident import Incident
from app.services.dispatch_matching import VolunteerMatchingService
from app.services.volunteer_management import VolunteerManagementService

async def process_auto_dispatch(incident_id: int):
    """
    Background worker that runs the waterfall auto-dispatch logic.
    - Generates recommendations using VolunteerMatchingService (and Qwen).
    - Dispatches to top 1-2 volunteers immediately.
    - Waits 2 minutes.
    - Checks if anyone accepted. If not, dispatches to the 3rd volunteer.
    """
    
    # We yield control immediately to not block the event loop while doing heavy DB/Qwen tasks
    await asyncio.sleep(0)
    
    db: Session = SessionLocal()
    try:
        # 1. Generate Recommendations
        matching_service = VolunteerMatchingService(db)
        batch = matching_service.recommend_for_incident(incident_id, limit=3)
        
        if not batch.recommendations:
            return # No volunteers available

        # 2. Extract volunteer IDs in ranked order
        top_vols = [r.volunteer_id for r in batch.recommendations]
        
        # 3. Dispatch to Top 1-2 first
        management_service = VolunteerManagementService(db)
        incident = db.get(Incident, incident_id)
        if not incident:
            return
            
        message_text = f"EMERGENCY DISPATCH\nType: {incident.incident_type}\nLocation: {incident.location_text}\nSummary: {incident.summary}\nReply 'accept' to take this case."

        vols_to_alert_now = top_vols[:2] # Top 2
        for vol_id in vols_to_alert_now:
            try:
                management_service.create_dispatch_request(vol_id, message_text, incident_id)
            except Exception as e:
                print(f"Auto-dispatch failed for vol {vol_id}: {e}")
                
        if len(top_vols) <= 2:
            return # No one else to escalate to
            
        # 4. Wait 2 minutes (Waterfall Escalate)
        # In a real production environment with multiple workers, we would use Celery/Redis for this.
        # For this prototype, asyncio.sleep in a background task works fine.
        await asyncio.sleep(120) 
        
        # 5. Check if incident was accepted by someone already
        # To do this safely, we check if there are any DISPATCH_STATUS_ACCEPTED dispatches for this incident.
        db.refresh(incident)
        if incident.status == 'closed':
            return
            
        from app.models.volunteer import VolunteerDispatch, DISPATCH_STATUS_ACCEPTED
        accepted_dispatch = db.query(VolunteerDispatch).filter(
            VolunteerDispatch.incident_id == incident_id,
            VolunteerDispatch.status == DISPATCH_STATUS_ACCEPTED
        ).first()
        
        if accepted_dispatch:
            return # Someone accepted, no need to escalate!
            
        # 6. Escalate to the 3rd volunteer
        try:
            management_service.create_dispatch_request(top_vols[2], message_text, incident_id)
        except Exception as e:
            print(f"Auto-dispatch escalation failed for vol {top_vols[2]}: {e}")
            
    finally:
        db.close()
