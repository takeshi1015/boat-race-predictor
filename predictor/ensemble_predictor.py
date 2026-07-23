"""
Ensemble Predictor
Combines multiple prediction methods for robust predictions
"""

from typing import List, Dict, Any, Optional
from collections import Counter
import numpy as np

import config
from utils.logger import logger
from predictor.statistical_predictor import StatisticalPredictor
from predictor.ml_predictor import MLPredictor
from predictor.rule_predictor import RulePredictor


class EnsemblePredictor:
    """Ensemble predictor combining multiple methods"""
    
    def __init__(self):
        """Initialize ensemble predictor"""
        self.model_name = "ensemble_predictor"
        self.version = "1.0"
        self.statistical_predictor = StatisticalPredictor()
        self.ml_predictor = MLPredictor()
        self.rule_predictor = RulePredictor()
        
        # Weights for each method
        self.weights = config.PREDICTION_WEIGHTS
    
    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make ensemble prediction from multiple methods
        
        Args:
            race_data: Race information and player stats
            
        Returns:
            Final ensemble prediction
        """
        logger.info(f"Ensemble prediction for race {race_data.get('race_id', '')}")
        
        try:
            # Get predictions from each method
            stat_pred = self.statistical_predictor.predict(race_data)
            ml_pred = self.ml_predictor.predict(race_data)
            rule_pred = self.rule_predictor.predict(race_data)
            
            # Combine predictions
            final_pred = self._combine_predictions(
                stat_pred,
                ml_pred,
                rule_pred,
                race_data
            )
            
            return final_pred
            
        except Exception as e:
            logger.error(f"Error in ensemble prediction: {e}")
            return self._empty_prediction()
    
    def _combine_predictions(
        self,
        stat_pred: Dict[str, Any],
        ml_pred: Dict[str, Any],
        rule_pred: Dict[str, Any],
        race_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Combine predictions from multiple methods
        
        Args:
            stat_pred: Statistical prediction
            ml_pred: ML prediction
            rule_pred: Rule-based prediction
            race_data: Race data
            
        Returns:
            Combined prediction
        """
        predictions = [
            (stat_pred, self.weights.get("statistical", 0.25)),
            (ml_pred, self.weights.get("ml", 0.35)),
            (rule_pred, self.weights.get("rule_based", 0.20)),
        ]
        
        # Calculate weighted scores for each player
        player_weighted_scores = {}
        player_confidence_scores = {}
        
        entries = race_data.get("entries", [])
        player_ids = [e.get("player_id") for e in entries]
        
        for player_id in player_ids:
            player_weighted_scores[player_id] = 0.0
            player_confidence_scores[player_id] = 0.0
        
        # Weight predictions
        for pred, weight in predictions:
            if pred["prediction"]:
                for rank, player_id in enumerate(pred["prediction"]):
                    if player_id in player_weighted_scores:
                        # Higher rank (1st, 2nd, 3rd) gets more weight
                        rank_weight = (3 - rank) / 3
                        player_weighted_scores[player_id] += rank_weight * weight * 100
                        player_confidence_scores[player_id] += pred.get("confidence", 0.0) * weight
        
        # Get top 3 predictions
        sorted_players = sorted(
            player_weighted_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        if len(sorted_players) < 3:
            return self._empty_prediction()
        
        top_3_ids = [p[0] for p in sorted_players[:3]]
        top_3_scores = [p[1] for p in sorted_players[:3]]
        
        # Calculate final confidence
        final_confidence = (
            player_confidence_scores[top_3_ids[0]] +
            player_confidence_scores[top_3_ids[1]] +
            player_confidence_scores[top_3_ids[2]]
        ) / 3
        
        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top_3_ids,
            "confidence": min(final_confidence, 1.0),
            "details": {
                "weighted_scores": dict(sorted_players[:6]),
                "method": "ensemble (statistical + ml + rule-based)",
                "component_predictions": {
                    "statistical": stat_pred.get("prediction", []),
                    "ml": ml_pred.get("prediction", []),
                    "rule_based": rule_pred.get("prediction", []),
                },
            }
        }
    
    def _empty_prediction(self) -> Dict[str, Any]:
        """Return empty prediction"""
        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": [],
            "confidence": 0.0,
            "details": {}
        }
