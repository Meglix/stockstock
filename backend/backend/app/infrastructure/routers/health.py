from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def health():
    # Simple liveness check used by frontend/devops.
    return {"status": "ok"}
