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


class GoogleAuthRequest(BaseModel):
    code: str


class GoogleExchangeRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    access_token: str
    refresh_token: Optional[str] = None
    timezone: str = "UTC"
