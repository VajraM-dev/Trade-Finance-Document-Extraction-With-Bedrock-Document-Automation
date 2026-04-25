from pydantic import BaseModel, Field, SecretStr


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr


class MeResponse(BaseModel):
    user_id: str
    username: str
    role: str
    csrf_token: str


class PasswordChangeRequest(BaseModel):
    old_password: SecretStr
    new_password: SecretStr = Field(min_length=10)
