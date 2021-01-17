from typing import Any
from pydantic import BaseModel

class TokenRequest(BaseModel):
    username: str