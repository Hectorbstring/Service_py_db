import os
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

load_dotenv()

# ---- Configurações ----
DB_SERVER = os.getenv("SQL_SERVER")
DB_NAME = os.getenv("SQL_DB_NAME")
DB_USER = os.getenv("SQL_USER")
DB_PASSWORD = os.getenv("SQL_PASSWORD")
SECRET_SIGNATURE = os.getenv("FACETEC_SIGNATURE_SECRET")

# Exemplo de DSN (ajuste conforme o driver disponível)
DATABASE_URL = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}"
    "?driver=ODBC+Driver+17+for+SQL+Server"
)

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- FastAPI app ----
app = FastAPI(title="Facetec SQL DB Service")

# ---- SQLAlchemy Engine ----
engine = create_engine(DATABASE_URL, fast_executemany=True)

# ---- Helper para mascarar valores sensíveis ----
def mask_value(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    return "*" * (len(value) - visible) + value[-visible:]


@app.get("/dbservice/{third_party_reference}")
async def get_session(third_party_reference: str, request: Request):
    x_signature = request.headers.get("x-signature")
    logger.info(f"Incoming request for thirdPartyReference={mask_value(third_party_reference)}, signature={mask_value(x_signature)}")
    logger.info(x_signature)
    logger.info(SECRET_SIGNATURE)
    # ---- Autenticação ----
    if x_signature != SECRET_SIGNATURE:
        logger.warning("Invalid signature received")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        with engine.connect() as conn:
            # ---- Buscar sessões ----
            query = text("""
                SELECT * FROM FacetecSessions WHERE externalDatabaseRefID = :ref
            """)
            rows = conn.execute(query, {"ref": third_party_reference}).fetchall()

            if not rows:
                raise HTTPException(status_code=404, detail="Session not found")

            logger.info(f"Found {len(rows)} session(s) for thirdPartyReference={mask_value(third_party_reference)}")

            response = {
                "thirdPartyReference": third_party_reference,
                "liveness": None,
                "enrollment3d": None,
                "match3d2dIdscan": None
            }

            # ---- Iterar sobre cada item ----
            for index, row in enumerate(rows):
                path = getattr(row, "httpCallInfoPath", "")
                logger.info(f"Processing session index={index}, path={path}")

                # Campos JSON (precisam ser convertidos)
                result = json.loads(row.result) if row.result else {}
                data = json.loads(row.data) if row.data else {}
                additionalSessionData = json.loads(row.additionalSessionData) if row.additionalSessionData else {}

                if path == "/liveness-3d":
                    response["liveness"] = {
                        "date": row.callDataDate.isoformat() if row.callDataDate else None,
                        "additionalSessionData": additionalSessionData,
                        "result": result,
                        "auditTrailImage": result.get("auditTrailImage", ""),
                        "success": bool(row.success)
                    }

                elif path == "/enrollment-3d":
                    response["enrollment3d"] = {
                        "date": row.callDataDate.isoformat() if row.callDataDate else None,
                        "additionalSessionData": additionalSessionData,
                        "result": result,
                        "externalDatabaseRefID": row.externalDatabaseRefID,
                        "auditTrailImage": result.get("auditTrailImage", ""),
                        "success": bool(row.success)
                    }

                elif path == "/match-3d-2d-idscan":
                    response["match3d2dIdscan"] = {
                        "templateInfo": data.get("templateInfo", {}),
                        "photoIDTamperingEvidenceFrontImage": data.get("photoIDTamperingEvidenceFrontImage", ""),
                        "photoIDTamperingEvidenceBackImage": data.get("photoIDTamperingEvidenceBackImage", ""),
                        "userConfirmedExtractedData": data.get("userConfirmedExtractedData", {}),
                        "photoIDSecondarySignatureCrop": data.get("photoIDSecondarySignatureCrop", ""),
                        "autoExtractedOCRData": data.get("autoExtractedOCRData", {}),
                        "photoIDPrimarySignatureCrop": data.get("photoIDPrimarySignatureCrop", ""),
                        "photoIDFaceCrop": data.get("photoIDFaceCrop", ""),
                        "photoIDFrontImage": data.get("photoIDFrontImage", ""),
                        "photoIDBackImage": data.get("photoIDBackImage", "")
                    }

                else:
                    logger.warning(f"Unknown path found in session item: {path}")

            logger.info(f"Final response prepared for thirdPartyReference={mask_value(third_party_reference)}")

            return JSONResponse(content=jsonable_encoder(response))

    except SQLAlchemyError as e:
        logger.exception("Database query failed")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail=str(e))
