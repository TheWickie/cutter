from typing import Optional
from pydantic import BaseModel


class AdminUserUpsert(BaseModel):
    name: str
    display_name: Optional[str] = None
    id_code: Optional[str] = None
    number: Optional[str] = None
    passphrase: Optional[str] = None


class AdminDisplayQuery(BaseModel):
    display_name: str

