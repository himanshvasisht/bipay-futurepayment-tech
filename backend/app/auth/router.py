"""
Authentication router with biometric fingerprint authentication
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, timedelta
import uuid
from loguru import logger

from app.models.user import UserCreate, UserLogin, UserResponse, Token, UserBalance
from app.auth.biometric import biometric_auth, encode_fingerprint_template, validate_fingerprint_data
from app.database import get_users_collection, get_fingerprints_collection
from app.utils.security import get_password_hash, verify_password, create_access_token, generate_user_id
from app.config import settings

router = APIRouter()
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated user from JWT token"""
    try:
        from jose import JWTError, jwt
        
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
            
        users_collection = get_users_collection()
        user = await users_collection.find_one({"user_id": user_id})
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
            
        return user
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

@router.post("/register", response_model=dict)
async def register_user(user_data: UserCreate):
    """Register a new user with biometric fingerprint enrollment"""
    try:
        users_collection = get_users_collection()
        fingerprints_collection = get_fingerprints_collection()
        
        existing_user = await users_collection.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )
        
        if not validate_fingerprint_data(user_data.fingerprint_data):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid fingerprint data"
            )
        
        user_id = generate_user_id()
        hashed_password = get_password_hash(user_data.password)
        
        try:
            fingerprint_template = await biometric_auth.enroll_fingerprint(
                user_id, user_data.fingerprint_data
            )
            encoded_template = encode_fingerprint_template(fingerprint_template)
        except Exception as e:
            logger.error(f"Fingerprint enrollment failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to enroll fingerprint. Please try again."
            )
        
        user_doc = {
            "user_id": user_id,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "email": user_data.email,
            "phone_number": user_data.phone_number,
            "hashed_password": hashed_password,
            "balance": 1000.0,
            "is_active": True,
            "is_verified": False,
            "fingerprint_enrolled": True,
            "total_transactions": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await users_collection.insert_one(user_doc)
        
        fingerprint_doc = {
            "user_id": user_id,
            "template": encoded_template,
            "enrolled_at": datetime.utcnow(),
            "last_used": None
        }
        
        await fingerprints_collection.insert_one(fingerprint_doc)
        
        logger.info(f"✅ User {user_id} registered successfully")
        
        # Create a simple token for compatibility; prefer JWT in production
        from app.utils.security import create_access_token
        access_token = create_access_token({"sub": user_id})

        return {
            "success": True,
            "message": "User registered successfully",
            "user_id": user_id,
            "fingerprint_enrolled": True,
            "token": access_token,
            "access_token": access_token,
            "user": {
                "user_id": user_id,
                "first_name": user_doc["first_name"],
                "last_name": user_doc["last_name"],
                "email": user_doc["email"],
                "balance": user_doc["balance"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=Token)
async def login_user(login_data: UserLogin):
    """Authenticate user using biometric fingerprint"""
    try:
        users_collection = get_users_collection()
        fingerprints_collection = get_fingerprints_collection()
        
        user = await users_collection.find_one({"user_id": login_data.user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID"
            )
        
        if not user.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        fingerprint_doc = await fingerprints_collection.find_one({"user_id": login_data.user_id})
        if not fingerprint_doc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Fingerprint not enrolled"
            )
        
        from app.auth.biometric import decode_fingerprint_template
        stored_template = decode_fingerprint_template(fingerprint_doc["template"])
        
        is_authenticated = await biometric_auth.authenticate_fingerprint(
            login_data.user_id, stored_template, login_data.fingerprint_data
        )
        
        if not is_authenticated:
            logger.warning(f"Failed authentication attempt for user: {login_data.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Fingerprint authentication failed"
            )
        
        await fingerprints_collection.update_one(
            {"user_id": login_data.user_id},
            {"$set": {"last_used": datetime.utcnow()}}
        )
        
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": login_data.user_id}, expires_delta=access_token_expires
        )
        
        logger.info(f"✅ User {login_data.user_id} authenticated successfully")
        
        # Return token and user info for frontend convenience
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "token": access_token,
            "user": {
                "user_id": user["user_id"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "email": user["email"],
                "balance": user.get("balance", 0.0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    try:
        user_response = UserResponse(
            id=current_user["_id"],
            user_id=current_user["user_id"],
            first_name=current_user["first_name"],
            last_name=current_user["last_name"],
            email=current_user["email"],
            phone_number=current_user["phone_number"],
            balance=current_user["balance"],
            is_active=current_user["is_active"],
            is_verified=current_user["is_verified"],
            created_at=current_user["created_at"],
            updated_at=current_user["updated_at"]
        )
        
        return user_response
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )

@router.get("/balance", response_model=UserBalance)
async def get_user_balance(current_user: dict = Depends(get_current_user)):
    """Get current user balance"""
    try:
        return UserBalance(
            user_id=current_user["user_id"],
            balance=current_user["balance"]
        )
        
    except Exception as e:
        logger.error(f"Error getting user balance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve balance"
        )
