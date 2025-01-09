from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from v1.router import router_v1

app = FastAPI(
    docs_url="/v1/kr-tag/docs",
    redoc_url="/v1/kr-tag/redoc",
    openapi_url="/v1/kr-tag/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터를 등록합니다.
app.include_router(router_v1)