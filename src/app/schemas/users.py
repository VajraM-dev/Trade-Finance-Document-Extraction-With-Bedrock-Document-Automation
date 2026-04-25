import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, SecretStr


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: SecretStr = Field(min_length=10)
    role: str = "customer"


class UserPatchRequest(BaseModel):
    role: str | None = None
    status: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    status: str
    created_at: datetime


class ApiKeyMaskedResponse(BaseModel):
    id: uuid.UUID
    last_four: str
    status: str
    created_at: datetime


class ApiKeyPlaintextResponse(BaseModel):
    id: uuid.UUID
    api_key: str
    last_four: str
    created_at: datetime
