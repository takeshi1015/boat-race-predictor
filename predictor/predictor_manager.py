"""
Predictor Manager
Manages all prediction operations and selects best predictions
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import itertools

import config
from utils.logger import logger
from database.db_manager import get_db_manager
from predictor.ensemble_predictor import EnsemblePredictor


class PredictorManager:
    """Manages prediction operations"""
    
    def __init__(self):
        """Initialize predictor manager"""
        self.ensemble_predictor = EnsemblePredictor()
        self.db_manager = get_db_manager()
    
    def predict_races(
        self,
        races: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Make predictions for multiple races
        
        Args:
            races: List of race data
            
        Returns:
            Dictionary with high confidence and high odds predictions
        """
        logger.info(f"Making predictions for {len(races)} races")
        
        try:
            all_predictions = []
            
            for race in races:
                pred = self.ensemble_predictor.predict(race)
                if pred["prediction"]:
                    pred["race_id"] = race.get("race_id", "")
                    pred["race_number"] = race.get("race_number", 0)
                    all_predictions.append(pred)
            
            # Separate into high confidence and high odds
            high_confidence = self._select_high_confidence(all_predictions)
            high_odds = self._select_high_odds(all_predictions)
            
            return {
                "high_confidence": high_confidence[:config.HIGH_CONFIDENCE_RACES],
                "high_odds": high_odds[:config.HIGH_ODDS_RACES],
                "all_predictions": all_predictions,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error in prediction manager: {e}")
            return {
                "high_confidence": [],
                "high_odds": [],
                "all_predictions": [],
                "timestamp": datetime.now().isoformat(),
            }
    
    def _select_high_confidence(self, predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Select predictions with high confidence
        
        Args:
            predictions: List of predictions
            
        Returns:
            Sorted list of high confidence predictions
        """
        return sorted(
            predictions,
            key=lambda x: x.get("confidence", 0.0),
            reverse=True
        )
    
    def _select_high_odds(self, predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Select predictions with potentially high odds (longer shots)
        
        Args:
            predictions: List of predictions
            
        Returns:
            Sorted list by potential odds
        """
        # Sort by inverse confidence (lower confidence = higher odds potential)
        # But still maintain minimum quality threshold
        filtered = [
            p for p in predictions
            if p.get("confidence", 0.0) < 0.8
        ]
        
        return sorted(
            filtered,
            key=lambda x: 1.0 - x.get("confidence", 0.0),
            reverse=True
        )
    
    def save_predictions(
        self,
        predictions: Dict[str, Any],
        mode: str = "today"
    ) -> bool:
        """
        Save predictions to database
        
        Args:
            predictions: Predictions to save
            mode: 'today' or 'tomorrow'
            
        Returns:
            True if saved successfully
        """
        try:
            session = self.db_manager.get_session()
            
            for pred_list, pred_type in [
                (predictions.get("high_confidence", []), "high_confidence"),
                (predictions.get("high_odds", []), "high_odds"),
            ]:
                for pred in pred_list:
                    pred_data = {
                        "race_id": pred.get("race_id", ""),
                        "prediction_date": datetime.now(),
                        "prediction_type": pred_type,
                        "predicted_order": pred.get("prediction", []),
                        "confidence": pred.get("confidence", 0.0),
                        "estimated_odds": self._estimate_odds(pred.get("prediction", [])),
                        "model_version": pred.get("version", "1.0"),
                        "methods_used": list(pred.get("details", {}).get("component_predictions", {}).keys()),
                    }
                    
                    self.db_manager.add_prediction(session, pred_data)
            
            session.close()
            logger.info(f"Predictions saved: {len(predictions.get('high_confidence', []))} + {len(predictions.get('high_odds', []))}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving predictions: {e}")
            return False
    
    def _estimate_odds(self, prediction: List[Any]) -> float:
        """
        Estimate trifecta odds for a prediction
        
        Args:
            prediction: Predicted finish order
            
        Returns:
            Estimated odds
        """
        if not prediction or len(prediction) < 3:
            return 10.0
        
        # Simple estimation based on player positions
        # In reality, this would use actual odds data
        base_odds = 15.0
        
        # Adjust based on prediction positions
        for pos in prediction[:3]:
            if pos <= 3:
                base_odds *= 0.9
            elif pos <= 6:
                base_odds *= 1.1
        
        return max(base_odds, 10.0)
    
    def evaluate_predictions(
        self,
        predictions: List[Dict[str, Any]],
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate prediction accuracy
        
        Args:
            predictions: List of predictions
            results: Actual race results
            
        Returns:
            Evaluation metrics
        """
        total = len(predictions)
        hits = 0
        total_payout = 0.0
        
        for pred in predictions:
            race_id = pred.get("race_id", "")
            result = next((r for r in results if r.get("race_id") == race_id), None)
            
            if result:
                predicted = pred.get("prediction", [])
                actual = result.get("result", [])
                
                if predicted == actual:
                    hits += 1
                    total_payout += result.get("odds", 1.0)
        
        hit_rate = hits / total if total > 0 else 0.0
        recovery_rate = total_payout / total if total > 0 else 0.0
        
        return {
            "total_predictions": total,
            "hits": hits,
            "hit_rate": hit_rate,
            "recovery_rate": recovery_rate,
            "timestamp": datetime.now().isoformat(),
        }
