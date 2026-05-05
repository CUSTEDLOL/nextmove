from typing import Optional
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    timezone: str = "Asia/Singapore"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: Optional[str] = None


class GoogleExchangeRequest(BaseModel):
    code: str
    redirect_uri: str
    timezone: str = "UTC"
