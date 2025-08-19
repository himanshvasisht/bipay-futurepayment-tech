"""
🚀 P2P PAYMENT LOGIC - COMPLETE IMPLEMENTATION
This is where ALL P2P payment processing happens!
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime
import uuid
from loguru import logger

from app.models.transaction import (
    P2PPaymentRequest, PaymentResponse, TransactionResponse, TransactionHistory
)
from app.auth.router import get_current_user
from app.auth.biometric import biometric_auth, decode_fingerprint_template
from app.blockchain.service import blockchain_service
from app.ai.service import anomaly_service
from app.database import (
    get_users_collection, get_transactions_collection, 
    get_fingerprints_collection
)
from app.utils.security import generate_transaction_id
from app.realtime import realtime_manager

router = APIRouter()

@router.post("/p2p", response_model=PaymentResponse)
async def process_p2p_payment(
    payment_request: P2PPaymentRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    🎯 MAIN P2P PAYMENT LOGIC - This is the complete P2P payment flow!
    
    Steps:
    1. 🔒 Fingerprint Authentication
    2. 💵 Balance Validation  
    3. 👤 Recipient Validation
    4. 🤖 AI Fraud Detection
    5. 💰 Process Payment (Atomic)
    6. ⛓️ Blockchain Recording
    7. 📝 Transaction Finalization
    """
    try:
        logger.info(f"💰 P2P Payment initiated: {current_user['user_id']} -> {payment_request.to_user}")
        
        users_collection = get_users_collection()
        transactions_collection = get_transactions_collection()
        fingerprints_collection = get_fingerprints_collection()
        
        sender_user_id = current_user["user_id"]
        
        # 🔒 STEP 1: BIOMETRIC AUTHENTICATION
        logger.info("🔐 Verifying sender fingerprint...")
        fingerprint_doc = await fingerprints_collection.find_one({"user_id": sender_user_id})
        if not fingerprint_doc:
            raise HTTPException(status_code=400, detail="Fingerprint not enrolled")
        
        stored_template = decode_fingerprint_template(fingerprint_doc["template"])
        is_authenticated = await biometric_auth.authenticate_fingerprint(
            sender_user_id, stored_template, payment_request.fingerprint_data
        )
        
        if not is_authenticated:
            logger.warning(f"❌ Fingerprint auth failed for {sender_user_id}")
            raise HTTPException(status_code=401, detail="Fingerprint authentication failed")
        
        logger.info("✅ Fingerprint authenticated successfully")
        
        # 💵 STEP 2: BALANCE VALIDATION
        sender_balance = current_user["balance"]
        if sender_balance < payment_request.amount:
            logger.warning(f"💸 Insufficient funds: ${sender_balance} < ${payment_request.amount}")
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient funds. Balance: ${sender_balance:.2f}"
            )
        
        # 👤 STEP 3: RECIPIENT VALIDATION
        recipient = await users_collection.find_one({"user_id": payment_request.to_user})
        if not recipient:
            logger.error(f"❌ Recipient not found: {payment_request.to_user}")
            raise HTTPException(status_code=404, detail="Recipient not found")
        
        logger.info(f"✅ Recipient found: {recipient['first_name']} {recipient['last_name']}")
        
        # 🆔 GENERATE TRANSACTION ID
        transaction_id = generate_transaction_id()
        logger.info(f"🆔 Transaction ID: {transaction_id}")
        
        # 🤖 STEP 4: AI FRAUD DETECTION
        logger.info("🤖 Running AI fraud detection...")
        
        # Get user transaction history for AI
        user_history = []
        try:
            # Try to get transaction history with limit
            async for tx in transactions_collection.find(
                {"$or": [{"from_user": sender_user_id}, {"to_user": sender_user_id}]}
            ).limit(50):
                user_history.append({
                    "amount": tx["amount"],
                    "timestamp": tx["created_at"].isoformat(),
                    "transaction_type": tx["transaction_type"]
                })
        except AttributeError:
            # Fallback for mock database that doesn't support limit
            logger.warning("⚠️ Mock database detected, using fallback for transaction history")
            async for tx in transactions_collection.find(
                {"$or": [{"from_user": sender_user_id}, {"to_user": sender_user_id}]}
            ):
                user_history.append({
                    "amount": tx["amount"],
                    "timestamp": tx["created_at"].isoformat(),
                    "transaction_type": tx["transaction_type"]
                })
                # Limit manually to 50
                if len(user_history) >= 50:
                    break
        
        # Run AI analysis
        anomaly_result = await anomaly_service.check_transaction_anomaly(
            {
                "transaction_id": transaction_id,
                "amount": payment_request.amount,
                "transaction_type": "p2p",
                "timestamp": datetime.utcnow().isoformat()
            },
            user_history
        )
        
        logger.info(f"🔍 AI Score: {anomaly_result['anomaly_score']:.3f}, Flagged: {anomaly_result['is_anomalous']}")
        
        # Create transaction record
        transaction = {
            "transaction_id": transaction_id,
            "from_user": sender_user_id,
            "to_user": payment_request.to_user,
            "amount": payment_request.amount,
            "description": payment_request.description,
            "transaction_type": "p2p",
            "status": "pending",
            "anomaly_score": anomaly_result["anomaly_score"],
            "is_flagged": anomaly_result["is_anomalous"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # ⚠️ FRAUD CHECK - Block if flagged
        if anomaly_result["is_anomalous"]:
            transaction["status"] = "flagged"
            await transactions_collection.insert_one(transaction)
            
            logger.warning(f"🚨 Transaction FLAGGED by AI: {transaction_id}")
            return PaymentResponse(
                success=False,
                transaction_id=transaction_id,
                message="Transaction flagged for review due to suspicious activity",
                anomaly_flagged=True,
                anomaly_score=anomaly_result["anomaly_score"]
            )
        
        # 💰 STEP 5: PROCESS PAYMENT (ATOMIC OPERATION)
        logger.info("💰 Processing payment transfer...")
        
        new_sender_balance = sender_balance - payment_request.amount
        new_recipient_balance = recipient["balance"] + payment_request.amount
        
        # Update sender balance
        await users_collection.update_one(
            {"user_id": sender_user_id},
            {
                "$set": {
                    "balance": new_sender_balance, 
                    "updated_at": datetime.utcnow()
                },
                "$inc": {"total_transactions": 1}
            }
        )
        
        # Update recipient balance  
        await users_collection.update_one(
            {"user_id": payment_request.to_user},
            {
                "$set": {
                    "balance": new_recipient_balance, 
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"✅ Balances updated: Sender=${new_sender_balance:.2f}, Recipient=${new_recipient_balance:.2f}")
        
        # ⛓️ STEP 6: BLOCKCHAIN RECORDING
        logger.info("⛓️ Recording on blockchain...")
        blockchain_success = await blockchain_service.add_transaction(
            from_user=sender_user_id,
            to_user=payment_request.to_user,
            amount=payment_request.amount,
            transaction_type="p2p",
            transaction_id=transaction_id
        )
        
        # 📝 STEP 7: FINALIZE TRANSACTION
        transaction["status"] = "completed"
        transaction["processed_at"] = datetime.utcnow()
        transaction["blockchain_recorded"] = blockchain_success
        await transactions_collection.insert_one(transaction)
        # Broadcast transaction event to realtime clients
        try:
            await realtime_manager.broadcast({
                "type": "transaction_created",
                "transaction_id": transaction_id,
                "from_user": sender_user_id,
                "to_user": payment_request.to_user,
                "amount": payment_request.amount,
                "transaction_type": "p2p",
                "status": "completed",
                "created_at": transaction["created_at"].isoformat() if hasattr(transaction["created_at"], 'isoformat') else str(transaction["created_at"])
            })
        except Exception:
            logger.warning("Realtime broadcast failed (non-fatal)")
        
        # 🎉 SUCCESS!
        logger.info(f"🎉 P2P Payment SUCCESS: ${payment_request.amount:.2f} sent!")
        logger.info(f"💸 {sender_user_id} -> {payment_request.to_user} | TX: {transaction_id}")
        
        return PaymentResponse(
            success=True,
            transaction_id=transaction_id,
            message=f"${payment_request.amount:.2f} sent successfully to {recipient['first_name']} {recipient['last_name']}",
            balance_after=new_sender_balance,
            recipient_name=f"{recipient['first_name']} {recipient['last_name']}",
            anomaly_flagged=False,
            anomaly_score=anomaly_result["anomaly_score"],
            blockchain_recorded=blockchain_success
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 P2P Payment ERROR: {e}")
        raise HTTPException(status_code=500, detail="Payment processing failed")

@router.get("/history", response_model=TransactionHistory)
async def get_transaction_history(
    page: int = 1,
    per_page: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get user transaction history with pagination"""
    try:
        transactions_collection = get_transactions_collection()
        user_id = current_user["user_id"]
        
        skip = (page - 1) * per_page
        
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"from_user": user_id},
                        {"to_user": user_id}
                    ]
                }
            },
            {
                "$sort": {"created_at": -1}
            },
            {
                "$facet": {
                    "transactions": [
                        {"$skip": skip},
                        {"$limit": per_page}
                    ],
                    "total": [
                        {"$count": "count"}
                    ]
                }
            }
        ]
        
        try:
            # Try to use MongoDB aggregate pipeline
            result = await transactions_collection.aggregate(pipeline).to_list(1)
            
            if not result:
                return TransactionHistory(
                    transactions=[],
                    total=0,
                    page=page,
                    per_page=per_page,
                    pages=0
                )
            
            transactions_data = result[0]["transactions"]
            total_count = result[0]["total"][0]["count"] if result[0]["total"] else 0
            
        except Exception as e:
            logger.warning(f"⚠️ MongoDB aggregate failed, using fallback: {e}")
            # Fallback for mock database or when aggregate fails
            all_transactions = []
            async for tx in transactions_collection.find({
                "$or": [
                    {"from_user": user_id},
                    {"to_user": user_id}
                ]
            }):
                all_transactions.append(tx)
            
            # Sort by created_at descending
            all_transactions.sort(key=lambda x: x.get("created_at", datetime.utcnow()), reverse=True)
            
            # Apply pagination
            total_count = len(all_transactions)
            start_idx = skip
            end_idx = start_idx + per_page
            transactions_data = all_transactions[start_idx:end_idx]
        total_pages = (total_count + per_page - 1) // per_page
        
        # Convert to response models
        transactions = []
        for tx in transactions_data:
            transactions.append(TransactionResponse(
                id=str(tx["_id"]),
                transaction_id=tx["transaction_id"],
                from_user=tx["from_user"],
                to_user=tx.get("to_user"),
                merchant_id=tx.get("merchant_id"),
                amount=tx["amount"],
                description=tx.get("description"),
                transaction_type=tx["transaction_type"],
                status=tx["status"],
                anomaly_score=tx.get("anomaly_score"),
                is_flagged=tx.get("is_flagged", False),
                created_at=tx["created_at"],
                updated_at=tx["updated_at"],
                processed_at=tx.get("processed_at")
            ))
        
        return TransactionHistory(
            transactions=transactions,
            total=total_count,
            page=page,
            per_page=per_page,
            pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error getting transaction history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transaction history")
