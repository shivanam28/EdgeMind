from pydantic import BaseModel
from typing import Optional

class MemoryCreate(BaseModel):
    text: str
    category: Optional[str] = None       # None = infer automatically
    security_tier: Optional[str] = None  # None = classify automatically

class SearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 5
    category: Optional[str] = None
    security_tier: Optional[str] = None