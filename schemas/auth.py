from pydantic import BaseModel


class CallRequest(BaseModel):
    number: str


class VerifyNameRequest(BaseModel):
    number: str
    name: str


class ModeRequest(BaseModel):
    session_id: str
    mode: str
