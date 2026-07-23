"""
Rule-Based Predictor
Uses expert knowledge and pattern rules for predictions
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

import config
from utils.logger import logger


class RulePredictor:
    """Rule-based predictor using expert knowledge"""
    
    def __init__(self):
        """Initialize rule predictor"""
        self.model_name = "rule_predictor"
        self.version = "1.0"
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, Any]:
        """
        Load prediction rules based on expert knowledge
        
        Returns:
            Dictionary of rules
        """
        return {
            "high_win_rate": 0.50,  # Player with >50% win rate often wins
            "speed_advantage": 0.5,  # Speed difference threshold
            "boat_factor": 0.3,  # Boat performance weight
            "recent_form_factor": 0.4,  # Recent performance weight
            "position_factor": 0.2,  # Starting position weight
        }
    
    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make prediction using rule-based logic
        
        Args:
            race_data: Race information and player stats
            
        Returns:
            Prediction result with ranking and confidence
        """
        logger.info(f"Rule-based prediction for race {race_data.get('race_id', '')}")
        
        try:
            entries = race_data.get("entries", [])
            if not entries:
                return self._empty_prediction()
            
            # Apply rules
            predictions = self._apply_rules(entries, race_data)
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error in rule-based prediction: {e}")
            return self._empty_prediction()
    
    def _apply_rules(self, entries: List[Dict], race_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply prediction rules to entries
        
        Args:
            entries: List of player entries
            race_data: Race information
            
        Returns:
            Prediction result
        """
        player_scores = []
        
        for entry in entries:
            score = 0.0
            confidence_boost = 0.0
            
            # Rule 1: High win rate players tend to win
            win_rate = entry.get("win_rate", 0.0)
            if win_rate > self.rules["high_win_rate"]:
                score += 50
                confidence_boost += 0.1
            
            # Rule 2: Speed advantage
            avg_speed = entry.get("avg_speed", 0.0)
            if avg_speed > 6.5:  # High speed threshold
                score += 30
            
            # Rule 3: Boat quality
            boat_win_rate = entry.get("boat_win_rate", 0.0)
            if boat_win_rate > 0.45:
                score += 20
            
            # Rule 4: Recent form
            recent_form = entry.get("recent_form", 0.5)
            if recent_form > 0.6:
                score += 25
                confidence_boost += 0.05
            
            # Rule 5: Inside position advantage
            position = entry.get("position", 0)
            if position <= 3:
                score += 15
            
            player_scores.append({
                "player_id": entry.get("player_id"),
                "score": score,
                "confidence_boost": confidence_boost,
            })
        
        # Sort by score
        player_scores.sort(key=lambda x: x["score"], reverse=True)
        
        if len(player_scores) < 3:
            return self._empty_prediction()
        
        # Calculate overall confidence
        top_confidence_boost = player_scores[0]["confidence_boost"] + player_scores[1]["confidence_boost"] + player_scores[2]["confidence_boost"]
        base_confidence = min(player_scores[0]["score"] / 100.0, 1.0)
        final_confidence = min(base_confidence + top_confidence_boost / 3, 1.0)
        
        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": [p["player_id"] for p in player_scores[:3]],
            "confidence": final_confidence,
            "details": {
                "scores": player_scores[:6],
                "method": "rule_based_analysis",
                "rules_applied": list(self.rules.keys()),
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
    
    def add_rule(self, rule_name: str, rule_value: Any) -> None:
        """
        Add or update a prediction rule
        
        Args:
            rule_name: Name of the rule
            rule_value: Value for the rule
        """
        self.rules[rule_name] = rule_value
        logger.info(f"Rule added: {rule_name} = {rule_value}")
