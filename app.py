from fastapi.responses import JSONResponse
from datetime import datetime
import json

def serialize_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()  # ou str(obj) se preferir formato simples
    raise TypeError(f"Type {type(obj)} not serializable")

@app.get("/dbservice/{third_party_reference}")
async def get_session(third_party_reference: str, request: Request):
    x_signature = request.headers.get("x-signature")
    logger.info(f"Incoming request for thirdPartyReference={third_party_reference}, signature={x_signature}")

    # ---- Autenticação ----
    if x_signature != SECRET_SIGNATURE:
        logger.warning(f"Invalid signature. Expected: {SECRET_SIGNATURE}")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # ---- Verificar conexão MongoDB ----
    await check_mongo_connection()

    # ---- Buscar sessões ----
    sessions_cursor = db[COLLECTION].find({"externalDatabaseRefID": third_party_reference})
    sessions = await sessions_cursor.to_list(length=None)
    logger.info(f"Found {len(sessions)} session(s) for thirdPartyReference={third_party_reference}")

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

        if path == "/liveness":
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

    logger.info(f"Final response prepared for thirdPartyReference={third_party_reference}")

    # ---- Converter datetime para string ----
    return JSONResponse(content=json.loads(json.dumps(response, default=serialize_datetime)))
