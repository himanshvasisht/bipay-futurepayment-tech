"""
Complete Blockchain Service for BiPay
"""

import hashlib
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from loguru import logger
from app.config import settings

@dataclass
class Transaction:
    from_user: str
    to_user: str
    amount: float
    transaction_type: str
    timestamp: str
    transaction_id: str

@dataclass
class Block:
    index: int
    timestamp: str
    transactions: List[Transaction]
    previous_hash: str
    nonce: int = 0
    hash: str = ""

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.mining_reward = settings.mining_reward
        self.difficulty = settings.blockchain_difficulty
        self.create_genesis_block()
        logger.info("✅ Blockchain initialized")
    
    def create_genesis_block(self) -> None:
        genesis_block = Block(
            index=0,
            timestamp=datetime.utcnow().isoformat(),
            transactions=[],
            previous_hash="0",
            nonce=0
        )
        genesis_block.hash = self.calculate_hash(genesis_block)
        self.chain.append(genesis_block)
        logger.info("🎯 Genesis block created")
    
    def calculate_hash(self, block: Block) -> str:
        transactions_data = [asdict(tx) for tx in block.transactions]
        block_string = json.dumps({
            "index": block.index,
            "timestamp": block.timestamp,
            "transactions": transactions_data,
            "previous_hash": block.previous_hash,
            "nonce": block.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
    
    def get_latest_block(self) -> Block:
        return self.chain[-1] if self.chain else None
    
    def add_transaction(self, transaction: Transaction) -> bool:
        try:
            if not self._validate_transaction(transaction):
                return False
            self.pending_transactions.append(transaction)
            logger.info(f"➕ Transaction {transaction.transaction_id} added to pending")
            return True
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False
    
    def _validate_transaction(self, transaction: Transaction) -> bool:
        if not all([
            transaction.from_user,
            transaction.to_user,
            transaction.amount > 0,
            transaction.transaction_id
        ]):
            return False
        
        # Check for duplicates
        for block in self.chain:
            for tx in block.transactions:
                if tx.transaction_id == transaction.transaction_id:
                    return False
        return True
    
    def mine_pending_transactions(self, mining_reward_address: str = "system") -> Optional[Block]:
        try:
            if not self.pending_transactions:
                return None
            
            logger.info(f"⛏️ Mining {len(self.pending_transactions)} transactions...")
            
            reward_transaction = Transaction(
                from_user="system",
                to_user=mining_reward_address,
                amount=self.mining_reward,
                transaction_type="mining_reward",
                timestamp=datetime.utcnow().isoformat(),
                transaction_id=f"reward_{int(datetime.utcnow().timestamp() * 1000)}"
            )
            
            new_block = Block(
                index=len(self.chain),
                timestamp=datetime.utcnow().isoformat(),
                transactions=self.pending_transactions + [reward_transaction],
                previous_hash=self.get_latest_block().hash
            )
            
            self.mine_block(new_block)
            self.chain.append(new_block)
            self.pending_transactions = []
            
            logger.info(f"✅ Block {new_block.index} mined: {new_block.hash[:16]}...")
            return new_block
            
        except Exception as e:
            logger.error(f"Mining error: {e}")
            return None
    
    def mine_block(self, block: Block) -> None:
        target = "0" * self.difficulty
        while block.hash[:self.difficulty] != target:
            block.nonce += 1
            block.hash = self.calculate_hash(block)
    
    def is_chain_valid(self) -> bool:
        try:
            for i in range(1, len(self.chain)):
                current_block = self.chain[i]
                previous_block = self.chain[i - 1]
                
                if current_block.hash != self.calculate_hash(current_block):
                    return False
                if current_block.previous_hash != previous_block.hash:
                    return False
                if current_block.hash[:self.difficulty] != "0" * self.difficulty:
                    return False
            return True
        except:
            return False
    
    def get_blockchain_info(self) -> Dict:
        total_transactions = sum(len(block.transactions) for block in self.chain)
        return {
            "total_blocks": len(self.chain),
            "total_transactions": total_transactions,
            "pending_transactions": len(self.pending_transactions),
            "difficulty": self.difficulty,
            "mining_reward": self.mining_reward,
            "is_valid": self.is_chain_valid()
        }

class BlockchainService:
    def __init__(self):
        self.blockchain = Blockchain()
    
    async def add_transaction(self, from_user: str, to_user: str, amount: float,
                            transaction_type: str, transaction_id: str) -> bool:
        try:
            transaction = Transaction(
                from_user=from_user,
                to_user=to_user,
                amount=amount,
                transaction_type=transaction_type,
                timestamp=datetime.utcnow().isoformat(),
                transaction_id=transaction_id
            )
            
            success = self.blockchain.add_transaction(transaction)
            
            if success and len(self.blockchain.pending_transactions) >= 5:
                logger.info("🤖 Auto-mining triggered")
                await self.mine_block()
            
            return success
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False
    
    async def mine_block(self) -> Optional[Block]:
        return self.blockchain.mine_pending_transactions()
    
    async def get_blockchain_stats(self) -> Dict:
        return self.blockchain.get_blockchain_info()

blockchain_service = BlockchainService()
