from pydantic import BaseModel


class ProfilePatch(BaseModel):
    user_id: str
    patch: dict


class NoteBody(BaseModel):
    user_id: str
    note: str
