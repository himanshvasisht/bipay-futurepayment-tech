"""
Merchant Router - USB Fingerprint Scanner Integration
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, timedelta
from loguru import logger

from app.models.merchant import (
    MerchantCreate, MerchantLogin, MerchantResponse, 
    MerchantBalance, MerchantStats, PaymentRequest
)
from app.auth.biometric import biometric_auth, encode_fingerprint_template, decode_fingerprint_template
from app.database import (
    get_merchants_collection, get_transactions_collection,
    get_fingerprints_collection, get_users_collection
)
from app.utils.security import (
    get_password_hash, create_access_token,
    generate_merchant_id, generate_transaction_id
)
from app.config import settings
from app.blockchain.service import blockchain_service

router = APIRouter()
security = HTTPBearer()

async def get_current_merchant(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated merchant"""
    try:
        from jose import JWTError, jwt
        
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        merchant_id: str = payload.get("sub")
        
        if merchant_id is None or not merchant_id.startswith("merchant_"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid merchant authentication"
            )
            
        merchants_collection = get_merchants_collection()
        merchant = await merchants_collection.find_one({"merchant_id": merchant_id})
        
        if merchant is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Merchant not found"
            )
            
        return merchant
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

@router.post("/login")
async def merchant_login(login: MerchantLogin):
    """Merchant login using fingerprint to obtain access token"""
    try:
        merchants_collection = get_merchants_collection()
        fingerprints_collection = get_fingerprints_collection()

        merchant = await merchants_collection.find_one({"merchant_id": login.merchant_id})
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")

        fp_doc = await fingerprints_collection.find_one({"user_id": login.merchant_id})
        if not fp_doc:
            raise HTTPException(status_code=400, detail="Fingerprint not enrolled for this merchant")

        stored_template = decode_fingerprint_template(fp_doc["template"])
        is_match = await biometric_auth.authenticate_fingerprint(
            login.merchant_id, stored_template, login.fingerprint_data
        )
        if not is_match:
            raise HTTPException(status_code=401, detail="Fingerprint authentication failed")

        # Issue JWT
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        token = create_access_token(
            data={"sub": merchant["merchant_id"], "scope": "merchant"},
            expires_delta=access_token_expires,
        )

        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "merchant": {
                "merchant_id": merchant["merchant_id"],
                "business_name": merchant["business_name"],
                "balance": merchant.get("balance", 0.0),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merchant login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.post("/register")
async def register_merchant(merchant_data: MerchantCreate):
    """Register new merchant with fingerprint"""
    try:
        merchants_collection = get_merchants_collection()
        fingerprints_collection = get_fingerprints_collection()
        
        existing_merchant = await merchants_collection.find_one({"email": merchant_data.email})
        if existing_merchant:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Merchant with this email already exists"
            )
        
        merchant_id = generate_merchant_id()
        hashed_password = get_password_hash(merchant_data.password)
        
        fingerprint_template = await biometric_auth.enroll_fingerprint(
            merchant_id, merchant_data.fingerprint_data
        )
        encoded_template = encode_fingerprint_template(fingerprint_template)
        
        merchant_doc = {
            "merchant_id": merchant_id,
            "business_name": merchant_data.business_name,
            "owner_name": merchant_data.owner_name,
            "email": merchant_data.email,
            "phone_number": merchant_data.phone_number,
            "business_address": merchant_data.business_address,
            "business_category": merchant_data.business_category,
            "tax_id": merchant_data.tax_id,
            "hashed_password": hashed_password,
            "balance": 0.0,
            "is_active": True,
            "is_verified": False,
            "fingerprint_enrolled": True,
            "total_transactions": 0,
            "total_revenue": 0.0,
            "rating": 0.0,
            "verification_documents": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await merchants_collection.insert_one(merchant_doc)
        
        fingerprint_doc = {
            "user_id": merchant_id,
            "template": encoded_template,
            "enrolled_at": datetime.utcnow(),
            "last_used": None
        }
        
        await fingerprints_collection.insert_one(fingerprint_doc)
        
        logger.info(f"✅ Merchant {merchant_id} registered successfully")
        
        return {
            "success": True,
            "message": "Merchant registered successfully",
            "merchant_id": merchant_id
        }
        
    except Exception as e:
        logger.error(f"Merchant registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/fingerprint-capture")
async def capture_customer_fingerprint(
    fingerprint_data: bytes = Body(...),
    amount: float = Body(...),
    description: str = Body(None),
    current_merchant: dict = Depends(get_current_merchant)
):
    """
    🖱️ USB FINGERPRINT SCANNER PAYMENT PROCESSING
    This handles customer payments via USB fingerprint scanners at merchant locations
    """
    try:
        logger.info(f"🖱️ USB Scanner payment: ${amount} at {current_merchant['business_name']}")
        
        # Find user by fingerprint matching
        fingerprints_collection = get_fingerprints_collection()
        users_collection = get_users_collection()
        
        user_found = None
        async for fingerprint_doc in fingerprints_collection.find({}):
            try:
                user_id = fingerprint_doc["user_id"]
                
                # Skip merchant fingerprints
                if user_id.startswith("merchant_"):
                    continue
                
                stored_template = decode_fingerprint_template(fingerprint_doc["template"])
                
                # Try to match fingerprint
                is_match = await biometric_auth.authenticate_fingerprint(
                    user_id, stored_template, fingerprint_data
                )
                
                if is_match:
                    user_found = await users_collection.find_one({"user_id": user_id})
                    break
                    
            except Exception as e:
                logger.warning(f"Error matching fingerprint: {e}")
                continue
        
        if not user_found:
            raise HTTPException(
                status_code=404,
                detail="No registered user found with this fingerprint"
            )
        
        # Check balance
        if user_found["balance"] < amount:
            return {
                "success": False,
                "message": f"Insufficient funds. Balance: ${user_found['balance']:.2f}",
                "user_name": f"{user_found['first_name']} {user_found['last_name']}",
                "balance": user_found["balance"]
            }
        
        # Process payment
        transaction_id = generate_transaction_id()
        new_customer_balance = user_found["balance"] - amount
        new_merchant_balance = current_merchant["balance"] + amount
        
        # Update balances
        await users_collection.update_one(
            {"user_id": user_found["user_id"]},
            {"$set": {"balance": new_customer_balance, "updated_at": datetime.utcnow()}}
        )
        
        merchants_collection = get_merchants_collection()
        await merchants_collection.update_one(
            {"merchant_id": current_merchant["merchant_id"]},
            {
                "$set": {"balance": new_merchant_balance, "updated_at": datetime.utcnow()},
                "$inc": {"total_transactions": 1, "total_revenue": amount}
            }
        )
        
        # Record transaction
        transaction = {
            "transaction_id": transaction_id,
            "from_user": user_found["user_id"],
            "to_user": None,
            "merchant_id": current_merchant["merchant_id"],
            "amount": amount,
            "description": description or f"Payment to {current_merchant['business_name']}",
            "transaction_type": "merchant",
            "status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "processed_at": datetime.utcnow(),
            "payment_method": "usb_fingerprint_scanner"
        }
        
        transactions_collection = get_transactions_collection()
        await transactions_collection.insert_one(transaction)
        
        # Add to blockchain
        await blockchain_service.add_transaction(
            from_user=user_found["user_id"],
            to_user=current_merchant["merchant_id"],
            amount=amount,
            transaction_type="merchant",
            transaction_id=transaction_id
        )
        
        logger.info(f"✅ USB Scanner payment completed: {transaction_id}")
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "message": "Payment completed successfully",
            "user_name": f"{user_found['first_name']} {user_found['last_name']}",
            "amount": amount,
            "customer_balance_after": new_customer_balance,
            "merchant_balance_after": new_merchant_balance
        }
        
    except Exception as e:
        logger.error(f"USB Scanner payment error: {e}")
        raise HTTPException(status_code=500, detail="Payment processing failed")
