"""
Statistical Analysis Predictor
Uses historical statistics to predict race outcomes
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

import config
from utils.logger import logger
from database.db_manager import get_db_manager


class StatisticalPredictor:
    """Statistical analysis based predictor"""
    
    def __init__(self):
        """Initialize statistical predictor"""
        self.db_manager = get_db_manager()
        self.model_name = "statistical_predictor"
        self.version = "1.0"
    
    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make prediction based on statistical analysis
        
        Args:
            race_data: Race information and player stats
            
        Returns:
            Prediction result with ranking and confidence
        """
        logger.info(f"Statistical prediction for race {race_data.get('race_id', '')}")
        
        try:
            # Extract player entries
            entries = race_data.get("entries", [])
            if not entries:
                logger.warning("No entries found for prediction")
                return self._empty_prediction()
            
            # Score each player
            player_scores = []
            for entry in entries:
                score = self._calculate_player_score(entry, race_data)
                player_scores.append({
                    "player_id": entry.get("player_id"),
                    "position": entry.get("position"),
                    "score": score,
                })
            
            # Sort by score (descending)
            player_scores.sort(key=lambda x: x["score"], reverse=True)
            
            # Generate predictions
            predictions = self._generate_predictions(player_scores, race_data)
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error in statistical prediction: {e}")
            return self._empty_prediction()
    
    def _calculate_player_score(self, entry: Dict[str, Any], race_data: Dict[str, Any]) -> float:
        """
        Calculate score for a player in this race
        
        Args:
            entry: Player entry information
            race_data: Race information
            
        Returns:
            Numerical score
        """
        score = 0.0
        
        # Win rate (30%)
        win_rate = entry.get("win_rate", 0.0)
        score += win_rate * 30
        
        # Place rate (20%)
        place_rate = entry.get("place_rate", 0.0)
        score += place_rate * 20
        
        # Average speed (25%)
        avg_speed = entry.get("avg_speed", 0.0)
        avg_speed_normalized = min(avg_speed / 10.0, 1.0)  # Normalize
        score += avg_speed_normalized * 25
        
        # Recent form (15%)
        recent_form = entry.get("recent_form", 0.5)
        score += recent_form * 15
        
        # Boat performance (10%)
        boat_win_rate = entry.get("boat_win_rate", 0.0)
        score += boat_win_rate * 10
        
        return score
    
    def _generate_predictions(self, player_scores: List[Dict], race_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate 3連単 predictions from player scores
        
        Args:
            player_scores: List of scored players
            race_data: Race information
            
        Returns:
            Prediction data
        """
        if len(player_scores) < 3:
            return self._empty_prediction()
        
        # Top 3 for 1st, 2nd, 3rd
        top_3 = [p["player_id"] for p in player_scores[:3]]
        
        # Calculate confidence
        score_gap = player_scores[0]["score"] - player_scores[2]["score"]
        confidence = min(score_gap / 50.0, 1.0)  # Normalize
        
        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top_3,
            "confidence": confidence,
            "details": {
                "scores": player_scores[:6],
                "method": "statistical_analysis",
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
