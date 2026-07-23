"""
Task Scheduler
Schedules and automates all prediction tasks
"""

from typing import Optional, Dict, Any
from datetime import datetime, time
import schedule
import time as time_module
from threading import Thread

import config
from utils.logger import logger
from scraper.boat_race_scraper import BoatRaceScraper
from predictor.predictor_manager import PredictorManager
from notifier.notification_manager import NotificationManager
from learner.model_trainer import ModelTrainer
from learner.performance_analyzer import PerformanceAnalyzer


class TaskScheduler:
    """Schedules and manages prediction tasks"""
    
    def __init__(self):
        """Initialize task scheduler"""
        self.scraper = BoatRaceScraper()
        self.predictor_manager = PredictorManager()
        self.notifier = NotificationManager()
        self.trainer = ModelTrainer()
        self.analyzer = PerformanceAnalyzer()
        self.running = False
    
    def schedule_tasks(self) -> None:
        """
        Schedule all prediction tasks
        """
        logger.info("Scheduling prediction tasks")
        
        # Today's prediction (morning)
        schedule.every().day.at(config.SCHEDULE_TODAY).do(
            self._run_today_prediction
        )
        
        # Tomorrow's prediction (evening)
        schedule.every().day.at(config.SCHEDULE_TOMORROW).do(
            self._run_tomorrow_prediction
        )
        
        # Evaluate results (night)
        schedule.every().day.at(config.SCHEDULE_EVALUATE).do(
            self._run_evaluation
        )
        
        # Model retraining (weekly)
        schedule.every().monday.at("02:00").do(
            self._run_model_retraining
        )
        
        # Performance analysis (daily)
        schedule.every().day.at("23:00").do(
            self._run_performance_analysis
        )
        
        logger.info("Tasks scheduled successfully")
    
    def start(self) -> None:
        """
        Start the scheduler in a background thread
        """
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info("Starting scheduler")
        self.running = True
        
        # Schedule tasks
        self.schedule_tasks()
        
        # Run scheduler in background thread
        scheduler_thread = Thread(target=self._run_scheduler, daemon=True)
        scheduler_thread.start()
        
        logger.info("Scheduler started in background thread")
    
    def stop(self) -> None:
        """
        Stop the scheduler
        """
        logger.info("Stopping scheduler")
        self.running = False
        schedule.clear()
    
    def _run_scheduler(self) -> None:
        """
        Run the scheduler loop (internal method)
        """
        while self.running:
            schedule.run_pending()
            time_module.sleep(60)  # Check every minute
    
    def _run_today_prediction(self) -> None:
        """
        Run today's prediction task
        """
        logger.info("Running today's prediction task")
        
        try:
            # Scrape today's races
            races = self.scraper.get_race_schedule()
            
            if not races:
                logger.warning("No races found for today")
                return
            
            # Make predictions
            predictions = self.predictor_manager.predict_races(races)
            
            # Save predictions
            self.predictor_manager.save_predictions(predictions, mode="today")
            
            # Send notifications
            self.notifier.send_predictions(predictions, mode="today")
            
            logger.info(f"Today's prediction completed: {len(predictions.get('high_confidence', []))} high confidence predictions")
            
        except Exception as e:
            logger.error(f"Error in today's prediction task: {e}")
            self.notifier.send_alert(
                alert_type="error",
                title="今日の予想失敗",
                message=str(e)
            )
    
    def _run_tomorrow_prediction(self) -> None:
        """
        Run tomorrow's prediction task
        """
        logger.info("Running tomorrow's prediction task")
        
        try:
            from datetime import timedelta
            
            # Scrape tomorrow's races
            tomorrow = datetime.now() + timedelta(days=1)
            races = self.scraper.get_race_schedule(tomorrow)
            
            if not races:
                logger.warning("No races found for tomorrow")
                return
            
            # Make predictions
            predictions = self.predictor_manager.predict_races(races)
            
            # Save predictions
            self.predictor_manager.save_predictions(predictions, mode="tomorrow")
            
            # Send notifications
            self.notifier.send_predictions(predictions, mode="tomorrow")
            
            logger.info(f"Tomorrow's prediction completed: {len(predictions.get('high_confidence', []))} high confidence predictions")
            
        except Exception as e:
            logger.error(f"Error in tomorrow's prediction task: {e}")
            self.notifier.send_alert(
                alert_type="error",
                title="明日の予想失敗",
                message=str(e)
            )
    
    def _run_evaluation(self) -> None:
        """
        Run result evaluation task
        """
        logger.info("Running result evaluation task")
        
        try:
            # Get yesterday's results
            from datetime import timedelta
            yesterday = datetime.now() - timedelta(days=1)
            results = self.scraper.get_race_results(yesterday)
            
            if not results:
                logger.info("No results to evaluate")
                return
            
            # Evaluate predictions against results
            logger.info(f"Evaluated {len(results)} race results")
            
        except Exception as e:
            logger.error(f"Error in evaluation task: {e}")
    
    def _run_model_retraining(self) -> None:
        """
        Run model retraining task
        """
        logger.info("Running model retraining task")
        
        try:
            if not self.trainer.should_retrain():
                logger.info("Models don't need retraining yet")
                return
            
            # Prepare training data
            training_data = self.trainer.prepare_training_data(days=30)
            
            if training_data and training_data.get("num_samples", 0) > 100:
                # Train models
                self.trainer.train_neural_network(training_data)
                self.trainer.train_xgboost(training_data)
                self.trainer.train_lstm(training_data)
                
                logger.info("Model retraining completed")
                self.notifier.send_alert(
                    alert_type="info",
                    title="モデル再訓練完了",
                    message="機械学習モデルが正常に再訓練されました"
                )
            else:
                logger.warning("Insufficient training data")
            
        except Exception as e:
            logger.error(f"Error in model retraining task: {e}")
            self.notifier.send_alert(
                alert_type="error",
                title="モデル再訓練失敗",
                message=str(e)
            )
    
    def _run_performance_analysis(self) -> None:
        """
        Run performance analysis task
        """
        logger.info("Running performance analysis task")
        
        try:
            # Analyze performance
            performance = self.analyzer.analyze_prediction_performance(days=7)
            
            # Save report
            self.analyzer.save_performance_report()
            
            # Check if accuracy has dropped
            hit_rate = performance.get("hit_rate", 0.0)
            if hit_rate < config.ACCURACY_ALERT_THRESHOLD and config.ALERT_LOW_ACCURACY:
                self.notifier.send_alert(
                    alert_type="warning",
                    title="精度突下警告",
                    message=f"的中率: {hit_rate:.1%} ({config.ACCURACY_ALERT_THRESHOLD:.1%}以下)\\nモデル再訓練を推奨します。"
                )
            
            logger.info(f"Performance analysis completed: hit_rate={hit_rate:.1%}")
            
        except Exception as e:
            logger.error(f"Error in performance analysis task: {e}")
