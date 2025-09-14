from pydantic import BaseModel


class ChatSend(BaseModel):
    session_id: str
    message: str
