"""
User Data Models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=8)
    fingerprint_data: bytes

class UserLogin(BaseModel):
    user_id: str
    fingerprint_data: bytes

class UserResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    first_name: str
    last_name: str
    email: str
    phone_number: str
    balance: float
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    # Pydantic v2 model config
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

class UserBalance(BaseModel):
    user_id: str
    balance: float

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
