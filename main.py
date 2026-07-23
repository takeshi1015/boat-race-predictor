"""
Main application entry point
Boat Race Predictor - Automated boat race prediction system
"""

import sys
import argparse
from datetime import datetime

import config
from utils.logger import logger
from scheduler.task_scheduler import TaskScheduler


def main():
    """Main application entry point"""
    
    parser = argparse.ArgumentParser(
        description="Boat Race Predictor - Automated boat race prediction system"
    )
    parser.add_argument(
        "--mode",
        choices=["run", "predict-today", "predict-tomorrow", "analyze", "retrain"],
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
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def _run_scheduler():
    """Run the main scheduler in continuous mode"""
    logger.info("Starting scheduler in continuous mode")
    
    scheduler = TaskScheduler()
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
    
    scheduler = TaskScheduler()
    scheduler._run_today_prediction()
    
    logger.info("Today's prediction task completed")


def _predict_tomorrow():
    """Run tomorrow's prediction immediately"""
    logger.info("Running tomorrow's prediction task")
    
    scheduler = TaskScheduler()
    scheduler._run_tomorrow_prediction()
    
    logger.info("Tomorrow's prediction task completed")


def _analyze_performance():
    """Analyze and display current performance metrics"""
    logger.info("Analyzing prediction performance")
    
    scheduler = TaskScheduler()
    scheduler._run_performance_analysis()
    
    logger.info("Performance analysis completed")


def _retrain_models():
    """Retrain machine learning models immediately"""
    logger.info("Retraining models")
    
    scheduler = TaskScheduler()
    scheduler._run_model_retraining()
    
    logger.info("Model retraining completed")


if __name__ == "__main__":
    main()
