"""
AI Anomaly Detection Service for Fraud Prevention
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
from app.config import settings
import joblib
import os

class AnomalyDetectionService:
    def __init__(self):
        # Initialize a default model so training/prediction can proceed without a prior load
        self.model = IsolationForest(
            contamination=settings.anomaly_contamination,
            random_state=42,
            n_estimators=100,
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.contamination = settings.anomaly_contamination
        self.threshold = settings.anomaly_threshold
        logger.info("🤖 AI Anomaly Detection Service initialized")
    
    async def initialize_model(self):
        """Initialize or load pre-trained model"""
        try:
            # Try to load existing model
            if os.path.exists('ai_model.pkl') and os.path.exists('scaler.pkl'):
                self.model = joblib.load('ai_model.pkl')
                self.scaler = joblib.load('scaler.pkl')
                self.is_trained = True
                logger.info("✅ AI model loaded from disk")
            else:
                # Create new model
                self.model = IsolationForest(
                    contamination=self.contamination,
                    random_state=42,
                    n_estimators=100
                )
                logger.info("🤖 New AI model created")
                
        except Exception as e:
            logger.error(f"Error initializing AI model: {e}")
            self.model = IsolationForest(contamination=self.contamination, random_state=42)
    
    def extract_features(self, transaction: Dict, user_history: List[Dict]) -> np.array:
        """Extract features from transaction and user history"""
        try:
            features = []
            
            # Transaction features
            amount = transaction.get('amount', 0)
            features.extend([
                amount,
                np.log1p(amount),  # Log transform of amount
                len(str(amount).split('.')[0]),  # Number of digits
                datetime.fromisoformat(transaction.get('timestamp', datetime.utcnow().isoformat())).hour,  # Hour of day
                datetime.fromisoformat(transaction.get('timestamp', datetime.utcnow().isoformat())).weekday(),  # Day of week
            ])
            
            # User history features
            if user_history:
                amounts = [tx.get('amount', 0) for tx in user_history]
                features.extend([
                    len(amounts),  # Transaction count
                    np.mean(amounts) if amounts else 0,  # Average amount
                    np.std(amounts) if len(amounts) > 1 else 0,  # Standard deviation
                    np.median(amounts) if amounts else 0,  # Median amount
                    max(amounts) if amounts else 0,  # Max amount
                    min(amounts) if amounts else 0,  # Min amount
                ])
                
                # Time-based features
                timestamps = []
                for tx in user_history:
                    try:
                        ts = datetime.fromisoformat(tx.get('timestamp', ''))
                        timestamps.append(ts)
                    except:
                        continue
                
                if timestamps:
                    timestamps.sort()
                    time_diffs = [(timestamps[i] - timestamps[i-1]).total_seconds() 
                                  for i in range(1, len(timestamps))]
                    
                    features.extend([
                        np.mean(time_diffs) if time_diffs else 0,  # Average time between transactions
                        np.std(time_diffs) if len(time_diffs) > 1 else 0,  # Std of time diffs
                        len([td for td in time_diffs if td < 300]) / len(time_diffs) if time_diffs else 0,  # Rapid transactions ratio
                    ])
                else:
                    features.extend([0, 0, 0])
            else:
                # No history - suspicious for new users with large amounts
                features.extend([0, 0, 0, 0, 0, 0, 0, 0, 0])
            
            # Velocity features (transactions in last hour/day)
            current_time = datetime.fromisoformat(transaction.get('timestamp', datetime.utcnow().isoformat()))
            last_hour_count = 0
            last_day_count = 0
            last_hour_amount = 0
            last_day_amount = 0
            
            for tx in user_history:
                try:
                    tx_time = datetime.fromisoformat(tx.get('timestamp', ''))
                    time_diff = (current_time - tx_time).total_seconds()
                    
                    if time_diff <= 3600:  # Last hour
                        last_hour_count += 1
                        last_hour_amount += tx.get('amount', 0)
                    
                    if time_diff <= 86400:  # Last day
                        last_day_count += 1
                        last_day_amount += tx.get('amount', 0)
                        
                except:
                    continue
            
            features.extend([
                last_hour_count,
                last_day_count, 
                last_hour_amount,
                last_day_amount,
            ])
            
            return np.array(features).reshape(1, -1)
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            # Return default features if extraction fails
            # The number of features here must match the number above (23)
            return np.zeros((1, 23))
    
    async def check_transaction_anomaly(self, transaction: Dict, user_history: List[Dict]) -> Dict[str, Any]:
        """Check if transaction is anomalous"""
        try:
            logger.info(f"🔍 Analyzing transaction: {transaction.get('transaction_id', 'unknown')}")
            
            # Extract features
            features = self.extract_features(transaction, user_history)
            
            if not self.is_trained:
                # Train model with basic data if not trained
                await self._train_with_basic_data()
            
            # Predict anomaly
            anomaly_score = self.model.decision_function(features)[0]
            is_outlier = self.model.predict(features) == -1
            
            # Normalize score to 0-1 range (higher = more suspicious)
            normalized_score = max(0, min(1, (0.5 - anomaly_score) / 1.0))
            
            # Additional rule-based checks
            amount = transaction.get('amount', 0)
            risk_factors = []
            
            # Large amount check
            if amount > 5000:
                risk_factors.append("large_amount")
                normalized_score += 0.2
            
            # Velocity check
            if len(user_history) == 0 and amount > 1000:
                risk_factors.append("new_user_large_amount")
                normalized_score += 0.3
            
            # Time-based checks
            tx_time = datetime.fromisoformat(transaction.get('timestamp', datetime.utcnow().isoformat()))
            if tx_time.hour < 6 or tx_time.hour > 23:
                risk_factors.append("unusual_time")
                normalized_score += 0.1
            
            # Rapid transactions
            if len(user_history) > 0:
                recent_transactions = [
                    tx for tx in user_history
                    if (tx_time - datetime.fromisoformat(tx.get('timestamp', ''))).total_seconds() < 300
                ]
                if len(recent_transactions) > 3:
                    risk_factors.append("rapid_transactions")
                    normalized_score += 0.2
            
            # Cap the score
            normalized_score = min(1.0, normalized_score)
            
            is_anomalous = normalized_score > self.threshold or is_outlier
            
            result = {
                "transaction_id": transaction.get('transaction_id'),
                "anomaly_score": round(normalized_score, 4),
                "is_anomalous": is_anomalous,
                "risk_factors": risk_factors,
                "model_prediction": "outlier" if is_outlier else "normal",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"🔍 Analysis complete: Score={normalized_score:.3f}, Anomalous={is_anomalous}")
            
            if is_anomalous:
                logger.warning(f"🚨 ANOMALY DETECTED: {transaction.get('transaction_id')} - Score: {normalized_score:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return {
                "transaction_id": transaction.get('transaction_id'),
                "anomaly_score": 0.0,
                "is_anomalous": False,
                "risk_factors": ["analysis_error"],
                "model_prediction": "error",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _train_with_basic_data(self):
        """Train model with synthetic basic data"""
        try:
            logger.info("🤖 Training AI model with basic data...")
            
            # Generate synthetic training data
            np.random.seed(42)
            n_samples = 1000
            
            # Normal transactions
            normal_features = []
            for _ in range(n_samples):
                features = [
                    np.random.lognormal(3, 1),      # amount
                    np.random.normal(3, 1),         # log amount
                    np.random.randint(1, 5),        # digits
                    np.random.randint(8, 22),       # hour
                    np.random.randint(0, 7),        # weekday
                    np.random.randint(1, 100),      # tx count
                    np.random.lognormal(3, 0.5),    # avg amount
                    np.random.exponential(50),      # std amount
                    np.random.lognormal(3, 0.5),    # median
                    np.random.lognormal(4, 1),      # max amount
                    np.random.lognormal(2, 0.5),    # min amount
                    np.random.exponential(3600),    # avg time diff
                    np.random.exponential(1800),    # std time diff
                    np.random.beta(0.1, 1),         # rapid ratio
                    np.random.poisson(1),           # last hour count
                    np.random.poisson(5),           # last day count
                    np.random.lognormal(3, 1),      # last hour amount
                    np.random.lognormal(4, 1),      # last day amount
                    0, 0, 0, 0, 0 # Padding for new features
                ]
                normal_features.append(features[:23])
            
            # Anomalous transactions (10%)
            anomaly_features = []
            for _ in range(n_samples // 10):
                features = [
                    np.random.lognormal(6, 1),      # large amounts
                    np.random.normal(6, 1),         # log amount
                    np.random.randint(4, 8),        # more digits
                    np.random.choice([2, 3, 4, 24, 1]), # unusual hours
                    np.random.randint(0, 7),        # weekday
                    np.random.randint(1, 10),       # low tx count
                    np.random.lognormal(5, 1),      # high avg
                    np.random.exponential(200),     # high std
                    np.random.lognormal(5, 1),      # high median
                    np.random.lognormal(7, 1),      # very high max
                    np.random.lognormal(4, 1),      # high min
                    np.random.exponential(300),     # rapid transactions
                    np.random.exponential(100),     # high std
                    np.random.beta(0.8, 0.2),       # high rapid ratio
                    np.random.poisson(10),          # many recent
                    np.random.poisson(20),          # many daily
                    np.random.lognormal(6, 1),      # high recent amount
                    np.random.lognormal(7, 1),      # high daily amount
                    0, 0, 0, 0, 0 # Padding for new features
                ]
                anomaly_features.append(features[:23])
            
            all_features = np.array(normal_features + anomaly_features)
            
            # Scale features
            all_features = self.scaler.fit_transform(all_features)
            
            # Train model
            self.model.fit(all_features)
            self.is_trained = True
            
            # Save model
            joblib.dump(self.model, 'ai_model.pkl')
            joblib.dump(self.scaler, 'scaler.pkl')
            
            logger.info("✅ AI model trained and saved")
            
        except Exception as e:
            logger.error(f"Error training AI model: {e}")
    
    async def get_anomaly_statistics(self) -> Dict[str, Any]:
        """Get anomaly detection statistics"""
        return {
            "model_status": "trained" if self.is_trained else "not_trained",
            "contamination": self.contamination,
            "threshold": self.threshold,
            "model_type": "IsolationForest" if self.model else "None"
        }

# NOTE: The global instance creation that was here has been removed.
# Create a global instance for importers (e.g., routers) to use directly
anomaly_service = AnomalyDetectionService()