from pydantic import BaseModel
from typing import Optional

class MemoryCreate(BaseModel):
    text: str
    category: Optional[str] = "general"
    security_tier: Optional[str] = None   # None = "let classify_data() decide"

class SearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 5
    category: Optional[str] = None
    security_tier: Optional[str] = None