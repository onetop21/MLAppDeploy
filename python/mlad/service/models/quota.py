from pydantic import BaseModel


class SetDefaultRequest(BaseModel):
    cpu: float
    gpu: int
    mem: str


class SetRequest(BaseModel):
    session: str
    cpu: float
    gpu: int
    mem: str
