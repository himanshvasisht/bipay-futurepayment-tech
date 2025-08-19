"""
Transaction Data Models
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TransactionType(str, Enum):
    P2P = "p2p"
    MERCHANT = "merchant"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    MINING_REWARD = "mining_reward"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    FLAGGED = "flagged"
    CANCELLED = "cancelled"

class P2PPaymentRequest(BaseModel):
    to_user: str = Field(..., description="Recipient user ID")
    amount: float = Field(..., gt=0, description="Payment amount")
    description: Optional[str] = Field(None, max_length=200)
    fingerprint_data: bytes = Field(..., description="Sender's fingerprint for authentication")

class MerchantPaymentRequest(BaseModel):
    merchant_id: str = Field(..., description="Merchant ID")
    amount: float = Field(..., gt=0, description="Payment amount")
    description: Optional[str] = Field(None, max_length=200)
    fingerprint_data: bytes = Field(..., description="Customer's fingerprint for authentication")

class PaymentResponse(BaseModel):
    success: bool
    transaction_id: str
    message: str
    balance_after: Optional[float] = None
    recipient_name: Optional[str] = None
    anomaly_flagged: bool = False
    anomaly_score: Optional[float] = None
    blockchain_recorded: bool = False

class TransactionResponse(BaseModel):
    id: str
    transaction_id: str
    from_user: str
    to_user: Optional[str]
    merchant_id: Optional[str] = None
    amount: float
    description: Optional[str]
    transaction_type: TransactionType
    status: TransactionStatus
    blockchain_hash: Optional[str] = None
    anomaly_score: Optional[float] = None
    is_flagged: bool = False
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

class TransactionHistory(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    page: int
    per_page: int
    pages: int
