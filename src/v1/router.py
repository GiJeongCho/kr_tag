from fastapi import APIRouter, status, Request
from pydantic import BaseModel
from .main import process_text

router_v1 = APIRouter(
    prefix="/v1",
    tags=["kr_tag"],
    responses={
        status.HTTP_200_OK: {"description": "Successful Response"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Not found"}
    },
)

class PosTypesRequest(BaseModel):
    text: str

@router_v1.post("/pos-types", summary="POS 유형 판단 [입력된 문장에서 사용된 문장과 각 품사의 종류 반환]")
async def pos_types_endpoint(req: PosTypesRequest, request: Request):
    print(f"Request received from {request.client.host}")
    result = await process_text(req.text)
    return result

