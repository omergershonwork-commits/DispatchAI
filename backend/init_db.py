import logging
from app.db.session import engine, Base
from app.models.incident import Incident
from app.models.volunteer import Volunteer, VolunteerDispatch
from app.models.dispatch import DispatchRecommendation

def init_db():
    print("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

if __name__ == "__main__":
    init_db()
