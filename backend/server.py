from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import bcrypt
import jwt

from timesheets import create_router as create_timesheet_router, ensure_indexes as ensure_timesheet_indexes

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Secret
JWT_SECRET = os.environ.get('JWT_SECRET', 'powerclean-secret-key-2024')

# SMTP / inquiry notification settings
SMTP_HOST = os.environ.get('SMTP_HOST')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER)
INQUIRY_NOTIFY_EMAIL = os.environ.get('INQUIRY_NOTIFY_EMAIL', 'batutta@msn.com')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ============= MODELS =============

class InquiryCreate(BaseModel):
    services: List[str]
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    description: Optional[str] = None
    consent: bool

class Inquiry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    services: List[str]
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    description: Optional[str] = None
    consent: bool
    status: str = "neu"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None

class InquiryUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminCreate(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str
    username: str

# ============= AUTH HELPERS =============

def send_inquiry_notification(inquiry: "Inquiry"):
    """Send an email notification for a newly submitted inquiry.
    Runs as a background task so a mail failure never breaks the form submission."""
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP is not configured (SMTP_HOST/SMTP_USER/SMTP_PASSWORD) - skipping inquiry notification email")
        return

    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"Neue Anfrage: {inquiry.name}"
        msg['From'] = SMTP_FROM
        msg['To'] = INQUIRY_NOTIFY_EMAIL

        body = (
            "Es ist eine neue Anfrage über das Formular eingegangen:\n\n"
            f"Name: {inquiry.name}\n"
            f"E-Mail: {inquiry.email}\n"
            f"Telefon: {inquiry.phone or '-'}\n"
            f"Adresse: {inquiry.address or '-'}\n"
            f"Leistungen: {', '.join(inquiry.services) if inquiry.services else '-'}\n"
            f"Wunschtermin: {inquiry.preferred_date or '-'} {inquiry.preferred_time or ''}\n"
            f"Beschreibung: {inquiry.description or '-'}\n"
        )
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Inquiry notification email sent for inquiry {inquiry.id}")
    except Exception as e:
        logger.error(f"Failed to send inquiry notification email for inquiry {inquiry.id}: {e}")


async def get_admin_user(token: str = None):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    try:
        payload = jwt.decode(token.replace("Bearer ", ""), JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============= PUBLIC ROUTES =============

@api_router.get("/")
async def root():
    return {"message": "PowerCleanService API"}

@api_router.post("/inquiries", response_model=Inquiry)
async def create_inquiry(input: InquiryCreate, background_tasks: BackgroundTasks):
    if not input.consent:
        raise HTTPException(status_code=400, detail="Consent is required")

    inquiry_obj = Inquiry(**input.model_dump())
    doc = inquiry_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()

    await db.inquiries.insert_one(doc)
    background_tasks.add_task(send_inquiry_notification, inquiry_obj)
    return inquiry_obj

@api_router.get("/services")
async def get_services():
    return {
        "services": [
            {"id": "baureinigung", "name": "Baureinigung"},
            {"id": "industriereinigung", "name": "Industriereinigung"},
            {"id": "fassadenreinigung", "name": "Fassadenreinigung"},
            {"id": "fenster-glasreinigung", "name": "Fenster- & Glasreinigung"},
            {"id": "unterhaltsreinigung", "name": "Unterhaltsreinigung"},
            {"id": "bueroreinigung", "name": "Büroreinigung"},
            {"id": "facility-management", "name": "Facility Management"},
            {"id": "hausmeisterdienste", "name": "Hausmeisterdienste"},
            {"id": "graffitientfernung", "name": "Graffitientfernung"},
            {"id": "eventmanagement", "name": "Eventmanagement (Reinigung)"},
            {"id": "gruen-aussenflaechenpflege", "name": "Grün- & Außenflächenpflege"},
            {"id": "fahrzeugreinigung", "name": "Fahrzeugreinigung"},
            {"id": "dach-photovoltaikreinigung", "name": "Dach- & Photovoltaikreinigung"},
            {"id": "baustellenueberwachung", "name": "Baustellenüberwachung"}
        ]
    }

# ============= ADMIN ROUTES =============

@api_router.post("/admin/login", response_model=TokenResponse)
async def admin_login(input: AdminLogin):
    admin = await db.admins.find_one({"username": input.username}, {"_id": 0})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(input.password.encode(), admin['password'].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = jwt.encode({
        "username": input.username,
        "exp": datetime.now(timezone.utc).timestamp() + 86400  # 24h
    }, JWT_SECRET, algorithm="HS256")
    
    return {"token": token, "username": input.username}

@api_router.post("/admin/setup")
async def admin_setup():
    existing = await db.admins.find_one({"username": "admin"}, {"_id": 0})
    if existing:
        return {"message": "Admin already exists", "created": False}
    
    hashed = bcrypt.hashpw("powerclean2024".encode(), bcrypt.gensalt()).decode()
    await db.admins.insert_one({
        "id": str(uuid.uuid4()),
        "username": "admin",
        "password": hashed
    })
    return {"message": "Admin created", "created": True, "username": "admin", "password": "powerclean2024"}

@api_router.get("/admin/inquiries")
async def get_all_inquiries(authorization: str = Header(None)):
    await get_admin_user(authorization)
    
    inquiries = await db.inquiries.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for inq in inquiries:
        if isinstance(inq.get('created_at'), str):
            inq['created_at'] = datetime.fromisoformat(inq['created_at'])
    return {"inquiries": inquiries}

@api_router.get("/admin/inquiries/{inquiry_id}")
async def get_inquiry(inquiry_id: str, authorization: str = Header(None)):
    await get_admin_user(authorization)
    
    inquiry = await db.inquiries.find_one({"id": inquiry_id}, {"_id": 0})
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return inquiry

@api_router.patch("/admin/inquiries/{inquiry_id}")
async def update_inquiry(inquiry_id: str, input: InquiryUpdate, authorization: str = Header(None)):
    await get_admin_user(authorization)
    
    update_data = {k: v for k, v in input.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    result = await db.inquiries.update_one({"id": inquiry_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    inquiry = await db.inquiries.find_one({"id": inquiry_id}, {"_id": 0})
    return inquiry

@api_router.delete("/admin/inquiries/{inquiry_id}")
async def delete_inquiry(inquiry_id: str, authorization: str = Header(None)):
    await get_admin_user(authorization)
    
    result = await db.inquiries.delete_one({"id": inquiry_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return {"message": "Inquiry deleted"}

@api_router.get("/admin/stats")
async def get_stats(authorization: str = Header(None)):
    await get_admin_user(authorization)
    
    total = await db.inquiries.count_documents({})
    neu = await db.inquiries.count_documents({"status": "neu"})
    bearbeitung = await db.inquiries.count_documents({"status": "in_bearbeitung"})
    erledigt = await db.inquiries.count_documents({"status": "erledigt"})
    
    return {
        "total": total,
        "neu": neu,
        "in_bearbeitung": bearbeitung,
        "erledigt": erledigt
    }

# Stundenzettel / Rechnungen (projects, calendar entries, PDFs)
api_router.include_router(create_timesheet_router(db, get_admin_user))

# Include the router in the main app
app.include_router(api_router)

origins_env = os.environ.get('CORS_ORIGINS', '')
allow_origins = origins_env.split(',') if origins_env else []

# Always ensure these common/production domains are allowed
default_origins = [
    "http://localhost:5173",
    "https://www.powercleanservice.de",
    "https://powercleanservice.de",
    "http://www.powercleanservice.de",
    "http://powercleanservice.de",
]
allow_origins.extend(default_origins)
allow_origins = list(set([o.strip() for o in allow_origins if o.strip()]))


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def create_db_indexes():
    try:
        await ensure_timesheet_indexes(db)
    except Exception as exc:  # never block startup because of index creation
        logger.warning(f"Could not create timesheet indexes: {exc}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
