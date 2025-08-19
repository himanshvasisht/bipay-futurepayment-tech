"""
Merchant Data Models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class MerchantCreate(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=200)
    owner_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., min_length=10, max_length=15)
    business_address: str = Field(..., min_length=10, max_length=500)
    business_category: str = Field(..., min_length=1, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=50)
    password: str = Field(..., min_length=8)
    fingerprint_data: bytes

class MerchantLogin(BaseModel):
    merchant_id: str
    fingerprint_data: bytes

class MerchantResponse(BaseModel):
    id: str = Field(alias="_id")
    merchant_id: str
    business_name: str
    owner_name: str
    email: str
    phone_number: str
    business_address: str
    business_category: str
    tax_id: Optional[str]
    balance: float
    is_active: bool
    is_verified: bool
    verification_documents: List[str]
    total_transactions: int
    total_revenue: float
    rating: float
    created_at: datetime
    updated_at: datetime
    # Pydantic v2 model config
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

class MerchantBalance(BaseModel):
    merchant_id: str
    balance: float
    total_revenue: float

class MerchantStats(BaseModel):
    merchant_id: str
    total_transactions: int
    total_revenue: float
    transactions_today: int
    revenue_today: float
    transactions_this_month: int
    revenue_this_month: float
    average_transaction_amount: float
    last_transaction_date: Optional[datetime]

class PaymentRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: Optional[str] = Field(None, max_length=200)
    customer_info: Optional[dict] = None

class Settlement(BaseModel):
    merchant_id: str
    amount: float
    settlement_date: datetime
    status: str
