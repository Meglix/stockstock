from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RefreshRequest(BaseModel):
    horizon: int = 30


class RetrainRequest(BaseModel):
    horizon: int = 30
    regenerate_dataset: bool = False
    seed: Optional[int] = 42
