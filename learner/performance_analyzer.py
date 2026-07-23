"""
Performance Analyzer
Analyzes and tracks model and prediction performance
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

import config
from utils.logger import logger
from database.db_manager import get_db_manager


class PerformanceAnalyzer:
    """Analyzes model and prediction performance"""
    
    def __init__(self):
        """Initialize performance analyzer"""
        self.db_manager = get_db_manager()
    
    def analyze_prediction_performance(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Analyze prediction performance over time period
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Performance metrics dictionary
        """
        logger.info(f"Analyzing prediction performance for last {days} days")
        
        try:
            session = self.db_manager.get_session()
            
            # Get recent predictions with results
            cutoff_date = datetime.now() - timedelta(days=days)
            from database.models import Prediction
            
            predictions = session.query(Prediction).filter(
                Prediction.prediction_date >= cutoff_date
            ).all()
            
            session.close()
            
            # Calculate metrics
            metrics = self._calculate_metrics(predictions)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return self._empty_metrics()
    
    def _calculate_metrics(self, predictions: List[Any]) -> Dict[str, Any]:
        """
        Calculate performance metrics
        
        Args:
            predictions: List of prediction records
            
        Returns:
            Metrics dictionary
        """
        if not predictions:
            return self._empty_metrics()
        
        total = len(predictions)
        hits = 0
        total_payoff = 0.0
        confidences = []
        odds_estimates = []
        actual_odds = []
        
        for pred in predictions:
            confidences.append(pred.confidence)
            odds_estimates.append(pred.estimated_odds)
            
            if pred.result:
                if pred.result.get("is_hit"):
                    hits += 1
                    total_payoff += pred.result.get("actual_odds", 0.0)
                    actual_odds.append(pred.result.get("actual_odds", 0.0))
        
        hit_rate = hits / total if total > 0 else 0.0
        recovery_rate = total_payoff / total if total > 0 else 0.0
        
        # Calculate confidence statistics
        avg_confidence = statistics.mean(confidences) if confidences else 0.0
        confidence_variance = statistics.variance(confidences) if len(confidences) > 1 else 0.0
        
        # Calculate odds statistics
        avg_estimated_odds = statistics.mean(odds_estimates) if odds_estimates else 0.0
        avg_actual_odds = statistics.mean(actual_odds) if actual_odds else 0.0
        
        return {
            "total_predictions": total,
            "hits": hits,
            "hit_rate": hit_rate,
            "recovery_rate": recovery_rate,
            "average_confidence": avg_confidence,
            "confidence_variance": confidence_variance,
            "average_estimated_odds": avg_estimated_odds,
            "average_actual_odds": avg_actual_odds,
            "analysis_period_days": 7,
            "timestamp": datetime.now().isoformat(),
        }
    
    def analyze_by_model(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """
        Analyze performance by prediction model
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Performance metrics by model
        """
        logger.info(f"Analyzing performance by model for last {days} days")
        
        try:
            session = self.db_manager.get_session()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            from database.models import Prediction
            
            predictions = session.query(Prediction).filter(
                Prediction.prediction_date >= cutoff_date
            ).all()
            
            session.close()
            
            # Group by model
            by_model = defaultdict(list)
            for pred in predictions:
                model = pred.details.get("method", "unknown") if pred.details else "unknown"
                by_model[model].append(pred)
            
            # Calculate metrics for each model
            model_metrics = {}
            for model, preds in by_model.items():
                model_metrics[model] = self._calculate_metrics(preds)
            
            return model_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing by model: {e}")
            return {}
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics dictionary"""
        return {
            "total_predictions": 0,
            "hits": 0,
            "hit_rate": 0.0,
            "recovery_rate": 0.0,
            "average_confidence": 0.0,
            "average_estimated_odds": 0.0,
            "timestamp": datetime.now().isoformat(),
        }
    
    def save_performance_report(
        self,
        filepath: str = "performance_report.json"
    ) -> bool:
        """
        Save performance report to file
        
        Args:
            filepath: Path to save report
            
        Returns:
            True if saved successfully
        """
        try:
            import json
            
            # Compile comprehensive report
            report = {
                "overall": self.analyze_prediction_performance(),
                "by_model": self.analyze_by_model(),
                "generated_at": datetime.now().isoformat(),
            }
            
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Performance report saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving performance report: {e}")
            return False
