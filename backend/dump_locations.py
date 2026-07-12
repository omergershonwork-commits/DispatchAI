import asyncio
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.incident import Incident
from app.models.volunteer import Volunteer

async def dump_data():
    async with async_session_maker() as session:
        result = await session.execute(select(Incident))
        incidents = result.scalars().all()
        for i in incidents:
            print(f"INCIDENT {i.id}: location_text='{i.location_text}'")
            
        result = await session.execute(select(Volunteer))
        volunteers = result.scalars().all()
        for v in volunteers:
            print(f"VOLUNTEER {v.id}: metadata_json={v.metadata_json}")

if __name__ == "__main__":
    asyncio.run(dump_data())
