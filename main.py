"""
Main application entry point
Boat Race Predictor - Automated boat race prediction system
"""

import sys
import argparse
from datetime import datetime
from typing import Any, Dict, List

import config
from utils.logger import logger
from predictor.ml_models import LogisticRegressionModel, RandomForestModel, NeuralNetworkModel
from predictor.rule_based_model import RuleBasedModel
from predictor.statistical_model import StatisticalModel


def main():
    """Main application entry point"""
    
    parser = argparse.ArgumentParser(
        description="Boat Race Predictor - Automated boat race prediction system"
    )
    parser.add_argument(
        "--mode",
        choices=["run", "predict-today", "predict-tomorrow", "analyze", "retrain", "predict"],
        default="run",
        help="Operation mode"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        config.DEBUG = True
        config.LOG_LEVEL = "DEBUG"
    
    logger.info("=" * 80)
    logger.info("Boat Race Predictor Started")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    try:
        if args.mode == "run":
            _run_scheduler()
        elif args.mode == "predict-today":
            _predict_today()
        elif args.mode == "predict-tomorrow":
            _predict_tomorrow()
        elif args.mode == "analyze":
            _analyze_performance()
        elif args.mode == "retrain":
            _retrain_models()
        elif args.mode == "predict":
            _run_all_models_demo()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def run_all_predictions(race_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run predictions across all available models for the given race.

    This is the unified interface that executes all prediction models
    (ML, rule-based, statistical) and aggregates their results.

    Args:
        race_data: Dictionary containing race information and participant
            entries.  Must include at minimum an 'entries' key with a list
            of entry dictionaries.

    Returns:
        Dictionary mapping each model name to its full prediction result.
        Also includes an 'ensemble' key with a simple majority-vote
        aggregation of the individual predictions.
    """
    models = {
        "logistic_regression": LogisticRegressionModel(),
        "random_forest": RandomForestModel(),
        "neural_network": NeuralNetworkModel(),
        "rule_based": RuleBasedModel(),
        "statistical": StatisticalModel(),
    }

    results: Dict[str, Any] = {}
    for name, model in models.items():
        try:
            results[name] = model.predict(race_data)
            logger.info("Prediction from %s: %s", name, results[name].get("prediction"))
        except Exception as exc:
            logger.error("Model %s failed: %s", name, exc)
            results[name] = {"model": name, "prediction": [], "confidence": 0.0, "details": {}}

    results["ensemble"] = _ensemble_predictions(results)
    return results


def _ensemble_predictions(
    model_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Aggregate individual model predictions via weighted voting.

    Each model's top prediction receives votes weighted by the model's
    reported confidence.  The aggregated result is the ordering of
    candidates by their total vote score.

    Args:
        model_results: Dictionary of per-model prediction results.

    Returns:
        Ensemble prediction dictionary.
    """
    vote_scores: Dict[Any, float] = {}
    total_confidence = 0.0

    for name, result in model_results.items():
        if name == "ensemble":
            continue
        confidence = float(result.get("confidence", 0.0))
        prediction: List[Any] = result.get("prediction", [])
        for rank, candidate in enumerate(prediction[:3]):
            # Higher-ranked predictions get more credit
            weight = confidence * (3 - rank) / 3.0
            vote_scores[candidate] = vote_scores.get(candidate, 0.0) + weight
        total_confidence += confidence

    sorted_candidates = sorted(vote_scores, key=lambda c: vote_scores[c], reverse=True)
    avg_confidence = total_confidence / len(model_results) if model_results else 0.0

    return {
        "model": "ensemble",
        "version": "1.0",
        "prediction": sorted_candidates[:3],
        "confidence": min(avg_confidence, 1.0),
        "details": {
            "method": "weighted_vote",
            "vote_scores": {str(k): round(v, 4) for k, v in vote_scores.items()},
        },
    }


def _get_scheduler():
    """Create and return a TaskScheduler instance.

    The import is deferred to avoid the pre-existing broken import chain
    that exists in the scheduler package when loaded at module level.

    Returns:
        A new TaskScheduler instance.
    """
    from scheduler.task_scheduler import TaskScheduler
    return TaskScheduler()


def _run_scheduler():
    """Run the main scheduler in continuous mode"""
    logger.info("Starting scheduler in continuous mode")

    scheduler = _get_scheduler()
    scheduler.start()
    
    try:
        # Keep the application running
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
        scheduler.stop()
        logger.info("Scheduler stopped")


def _predict_today():
    """Run today's prediction immediately"""
    logger.info("Running today's prediction task")

    _get_scheduler()._run_today_prediction()
    
    logger.info("Today's prediction task completed")


def _predict_tomorrow():
    """Run tomorrow's prediction immediately"""
    logger.info("Running tomorrow's prediction task")

    _get_scheduler()._run_tomorrow_prediction()
    
    logger.info("Tomorrow's prediction task completed")


def _analyze_performance():
    """Analyze and display current performance metrics"""
    logger.info("Analyzing prediction performance")

    _get_scheduler()._run_performance_analysis()
    
    logger.info("Performance analysis completed")


def _retrain_models():
    """Retrain machine learning models immediately"""
    logger.info("Retraining models")

    _get_scheduler()._run_model_retraining()
    
    logger.info("Model retraining completed")


def _run_all_models_demo() -> None:
    """Demonstrate all prediction models with sample race data."""
    logger.info("Running all prediction models with sample data")

    sample_race: Dict[str, Any] = {
        "race_id": "demo-001",
        "race_number": 1,
        "location": "Kiryu",
        "wind_speed": 2.0,
        "wave_height": 5.0,
        "air_temperature": 22.0,
        "water_temperature": 20.0,
        "entries": [
            {
                "frame_number": 1,
                "player_id": "P001",
                "win_rate": 0.55,
                "place_rate": 0.70,
                "payoff_rate": 0.50,
                "avg_start_timing": 0.12,
                "recent_results": ["1", "2", "1", "3", "1"],
                "rank": "A1",
                "flying_count": 0,
                "avg_speed": 6.8,
                "boat_win_rate": 0.50,
                "boat_place_rate": 0.65,
                "engine_rate": 0.70,
                "exhibition_time": 6.75,
            },
            {
                "frame_number": 2,
                "player_id": "P002",
                "win_rate": 0.40,
                "place_rate": 0.60,
                "payoff_rate": 0.38,
                "avg_start_timing": 0.18,
                "recent_results": ["2", "1", "3", "2", "4"],
                "rank": "A2",
                "flying_count": 0,
                "avg_speed": 6.6,
                "boat_win_rate": 0.42,
                "boat_place_rate": 0.58,
                "engine_rate": 0.60,
                "exhibition_time": 6.80,
            },
            {
                "frame_number": 3,
                "player_id": "P003",
                "win_rate": 0.30,
                "place_rate": 0.50,
                "payoff_rate": 0.28,
                "avg_start_timing": 0.20,
                "recent_results": ["3", "3", "2", "5", "3"],
                "rank": "B1",
                "flying_count": 1,
                "avg_speed": 6.3,
                "boat_win_rate": 0.35,
                "boat_place_rate": 0.50,
                "engine_rate": 0.50,
                "exhibition_time": 6.90,
            },
        ],
    }

    all_results = run_all_predictions(sample_race)
    for model_name, result in all_results.items():
        logger.info(
            "[%s] prediction=%s confidence=%.2f",
            model_name,
            result.get("prediction"),
            result.get("confidence", 0.0),
        )


if __name__ == "__main__":
    main()

