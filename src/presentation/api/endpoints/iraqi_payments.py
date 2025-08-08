from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

# SERVICE DISABLED: This feature is under development. Do not remove this placeholder.

router = APIRouter(tags=["iraqi-payments"])


@router.get("/status", tags=["Maintenance"])
async def service_unavailable():
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "هذه الخدمة غير متوفرة حالياً - سيتم تفعيلها قريباً.",
            "service": "iraqi_payment",
            "status": "maintenance",
        },
    )
