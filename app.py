import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder

load_dotenv()

# ---- Configurações ----
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME")
COLLECTION = os.getenv("MONGO_COLLECTION")
SECRET_SIGNATURE = os.getenv("FACETEC_SIGNATURE_SECRET")

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- FastAPI app ----
app = FastAPI(title="Facetec DB Service")

# ---- MongoDB client global ----
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DB_NAME]

# ---- Helper para checar conexão MongoDB ----
async def check_mongo_connection():
    try:
        await db.command({"ping": 1})
        logger.info("MongoDB already connected")
    except Exception:
        logger.info("MongoDB not connected. Connecting...")
        await mongo_client.admin.command({"ping": 1})
        logger.info("MongoDB connection established")

def mask_value(value: str, visible: int = 4) -> str:
    """Mascara um valor, deixando apenas os últimos `visible` caracteres legíveis."""
    if not value:
        return ""
    return "*" * (len(value) - visible) + value[-visible:]

@app.get("/dbservice/{third_party_reference}")
async def get_session(third_party_reference: str, request: Request):
    x_signature = request.headers.get("x-signature")
    logger.info(f"Incoming request for thirdPartyReference={mask_value(third_party_reference)}, signature={mask_value(x_signature)}")

    # ---- Autenticação ----
    if x_signature != SECRET_SIGNATURE:
        logger.warning(f"Invalid signature. Expected: {SECRET_SIGNATURE}")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # ---- Verificar conexão MongoDB ----
    await check_mongo_connection()

    # ---- Buscar sessões ----
    sessions_cursor = db[COLLECTION].find({"externalDatabaseRefID": third_party_reference})
    sessions = await sessions_cursor.to_list(length=None)
    logger.info(f"Found {len(sessions)} session(s) for thirdPartyReference={mask_value(third_party_reference)}")

    if not sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    response = {
        "liveness": None,
        "enrollment3d": None,
        "match3d2dIdscan": None
    }

    # ---- Iterar sobre cada item da sessão ----
    for index, item in enumerate(sessions):
        path = item.get("httpCallInfo", {}).get("path", "")
        logger.info(f"Processing session index={index}, path={path}")

        if path == "/liveness-3d":
            result = item.get("result", {})
            response["liveness"] = {
                "date": item.get("callData", {}).get("date"),
                "additionalSessionData": item.get("additionalSessionData"),
                "result": result,
                "auditTrailImage": result.get("auditTrailImage", ""),
                "ageEstimation": item.get("ageEstimation"),
                "success": item.get("success", False)
            }

        elif path == "/enrollment-3d":
            result = item.get("result", {})
            response["enrollment3d"] = {
                "date": item.get("callData", {}).get("date"),
                "additionalSessionData": item.get("additionalSessionData"),
                "result": result,
                "externalDatabaseRefID": item.get("externalDatabaseRefID"),
                "auditTrailImage": result.get("auditTrailImage", ""),
                "success": item.get("success", False)
            }

        elif path == "/match-3d-2d-idscan":
            data = item.get("data", {})
            response["match3d2dIdscan"] = {
                "idScanResultsSoFar": item.get("idScanResultsSoFar"),
                "templateInfo": data.get("templateInfo", {}),
                "photoIDTamperingEvidenceFrontImage": data.get("photoIDTamperingEvidenceFrontImage", ""),
                "photoIDTamperingEvidenceBackImage": data.get("photoIDTamperingEvidenceBackImage", ""),
                "userConfirmedExtractedData": data.get("userConfirmedExtractedData", {}),
                "photoIDSecondarySignatureCrop": data.get("photoIDSecondarySignatureCrop", ""),
                "extractedNFCImage": data.get("extractedNFCImage", ""),
                "autoExtractedOCRData": data.get("autoExtractedOCRData", {}),
                "photoIDPrimarySignatureCrop": data.get("photoIDPrimarySignatureCrop", ""),
                "photoIDFaceCrop": data.get("photoIDFaceCrop", ""),
                "photoIDFrontImage": data.get("photoIDFrontImage", ""),
                "photoIDFrontCrop": data.get("photoIDFrontCrop", ""),
                "photoIDBackImage": data.get("photoIDBackImage", ""),
                "photoIDBackCrop": data.get("photoIDBackCrop", "")
            }

        else:
            logger.warning(f"Unknown path found in session item: {path}")

    logger.info(f"Final response prepared for thirdPartyReference={mask_value(third_party_reference)}")

    # ---- Serializar corretamente datetime ----
    return JSONResponse(content=jsonable_encoder(response))