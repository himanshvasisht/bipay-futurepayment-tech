"""
Security utilities for authentication and authorization
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from loguru import logger
from app.config import settings
import uuid

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a plain password"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError as e:
        logger.error(f"Token verification failed: {e}")
        return None

def generate_user_id() -> str:
    """Generate unique user ID"""
    return f"user_{uuid.uuid4().hex[:12]}"

def generate_transaction_id() -> str:
    """Generate unique transaction ID"""
    return f"tx_{uuid.uuid4().hex[:16]}"

def generate_merchant_id() -> str:
    """Generate unique merchant ID"""
    return f"merchant_{uuid.uuid4().hex[:12]}"

def sanitize_input(input_string: str) -> str:
    """Sanitize input string to prevent injection attacks"""
    if not isinstance(input_string, str):
        return ""
    
    dangerous_chars = ['<', '>', '"', "'", '&', '%', '$', '#', '@', '!']
    for char in dangerous_chars:
        input_string = input_string.replace(char, '')
    
    return input_string.strip()

def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    import re
    cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if not cleaned_phone.isdigit():
        return False
    
    if len(cleaned_phone) < 10 or len(cleaned_phone) > 15:
        return False
    
    return True

def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """Mask sensitive data for logging"""
    if not data or len(data) <= visible_chars:
        return mask_char * len(data) if data else ""
    
    return data[:visible_chars] + mask_char * (len(data) - visible_chars)
