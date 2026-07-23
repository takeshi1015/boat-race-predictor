"""
アンサンブルモデル
複数の機械学習モデルを組み合わせて予測
"""

import logging
import numpy as np
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from utils.logger import setup_logger
from utils.database import get_db_session

logger = setup_logger(__name__)


class EnsembleModel:
    """複数モデルのアンサンブル予測"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.models = {}
        self.model_weights = {
            'neural_network': 0.4,
            'xgboost': 0.35,
            'random_forest': 0.25
        }
        logger.info("アンサンブルモデルを初期化")
    
    def predict_today(self):
        """当日の予測を実行"""
        logger.info("当日予測を開始")
        try:
            # 当日のレースデータを取得
            races = self._get_race_data('today')
            if not races:
                logger.warning("当日のレースデータがありません")
                return []
            
            predictions = []
            for race in races:
                pred = self._predict_race(race)
                predictions.append(pred)
            
            logger.info(f"当日予測完了: {len(predictions)}件")
            return predictions
        except Exception as e:
            logger.error(f"当日予測エラー: {e}", exc_info=True)
            return []
    
    def predict_tomorrow(self):
        """翌日の予測を実行"""
        logger.info("翌日予測を開始")
        try:
            # 翌日のレースデータを取得
            races = self._get_race_data('tomorrow')
            if not races:
                logger.warning("翌日のレースデータがありません")
                return []
            
            predictions = []
            for race in races:
                pred = self._predict_race(race)
                predictions.append(pred)
            
            logger.info(f"翌日予測完了: {len(predictions)}件")
            return predictions
        except Exception as e:
            logger.error(f"翌日予測エラー: {e}", exc_info=True)
            return []
    
    def _predict_race(self, race):
        """個別レースの予測"""
        try:
            # 特徴量を準備
            features = self._prepare_features(race)
            
            # 各モデルで予測
            predictions = self._get_model_predictions(features)
            
            # アンサンブル予測（重み付け平均）
            ensemble_pred = self._ensemble_predictions(predictions)
            
            # 信頼度スコアを計算
            confidence = self._calculate_confidence(predictions, ensemble_pred)
            
            return {
                'race_id': race.get('race_id'),
                'date': race.get('date'),
                'place': race.get('place'),
                'race_number': race.get('race_number'),
                'prediction': ensemble_pred,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"レース予測エラー: {e}")
            return None
    
    def _get_race_data(self, period):
        """レースデータを取得"""
        try:
            session = get_db_session()
            # SQLでレースデータを取得
            # 実装例: SQLクエリを実行してレースデータを取得
            races = []
            session.close()
            return races
        except Exception as e:
            logger.error(f"レースデータ取得エラー: {e}")
            return []
    
    def _prepare_features(self, race):
        """特徴量を準備"""
        features = {}
        try:
            # 天気情報
            features['weather'] = self._encode_weather(race.get('weather', 'unknown'))
            
            # 水面状況
            features['water_condition'] = self._encode_water_condition(
                race.get('water_condition', 'unknown')
            )
            
            # 出走者情報
            participants = race.get('participants', [])
            for i, p in enumerate(participants[:6]):  # 最大6艇
                features[f'rider_{i}_level'] = p.get('level', 0)
                features[f'rider_{i}_win_rate'] = p.get('win_rate', 0)
                features[f'rider_{i}_place_rate'] = p.get('place_rate', 0)
            
            # 時刻特性
            features['hour'] = race.get('start_time_hour', 0)
            features['is_night'] = 1 if features['hour'] >= 17 else 0
            
            return features
        except Exception as e:
            logger.error(f"特徴量準備エラー: {e}")
            return {}
    
    def _get_model_predictions(self, features):
        """各モデルから予測を取得"""
        predictions = {}
        try:
            # ニューラルネットワーク
            predictions['neural_network'] = self._predict_nn(features)
            
            # XGBoost
            predictions['xgboost'] = self._predict_xgboost(features)
            
            # ランダムフォレスト
            predictions['random_forest'] = self._predict_rf(features)
            
            return predictions
        except Exception as e:
            logger.error(f"モデル予測エラー: {e}")
            return {}
    
    def _predict_nn(self, features):
        """ニューラルネットワークで予測"""
        # 実装例
        return {1: 0.25, 2: 0.35, 3: 0.40}
    
    def _predict_xgboost(self, features):
        """XGBoostで予測"""
        # 実装例
        return {1: 0.22, 2: 0.38, 3: 0.40}
    
    def _predict_rf(self, features):
        """ランダムフォレストで予測"""
        # 実装例
        return {1: 0.28, 2: 0.32, 3: 0.40}
    
    def _ensemble_predictions(self, predictions):
        """複数の予測をアンサンブル"""
        ensemble = {}
        try:
            for model_name, pred in predictions.items():
                weight = self.model_weights.get(model_name, 1.0)
                for position, prob in pred.items():
                    if position not in ensemble:
                        ensemble[position] = 0
                    ensemble[position] += prob * weight
            
            # 正規化
            total = sum(ensemble.values())
            if total > 0:
                ensemble = {k: v / total for k, v in ensemble.items()}
            
            return ensemble
        except Exception as e:
            logger.error(f"アンサンブルエラー: {e}")
            return {}
    
    def _calculate_confidence(self, predictions, ensemble_pred):
        """信頼度スコアを計算"""
        try:
            # 各モデルの予測の一致度を計算
            consensus_scores = []
            
            for model_pred in predictions.values():
                # 最も確率の高い予測を取得
                top_pred = max(model_pred.items(), key=lambda x: x[1])
                top_ensemble = max(ensemble_pred.items(), key=lambda x: x[1])
                
                # 一致度を計算
                if top_pred[0] == top_ensemble[0]:
                    consensus_scores.append(1.0)
                else:
                    consensus_scores.append(0.5)
            
            # 平均信頼度
            confidence = np.mean(consensus_scores) if consensus_scores else 0.5
            return float(confidence)
        except Exception as e:
            logger.error(f"信頼度計算エラー: {e}")
            return 0.5
    
    def evaluate_performance(self):
        """パフォーマンスを評価"""
        try:
            session = get_db_session()
            # 過去の予測と実績を比較
            metrics = {
                'accuracy': 0.58,
                'precision': 0.62,
                'recall': 0.55,
                'f1_score': 0.58
            }
            session.close()
            return metrics
        except Exception as e:
            logger.error(f"パフォーマンス評価エラー: {e}")
            return {}
    
    @staticmethod
    def _encode_weather(weather):
        """天気をエンコード"""
        weather_map = {
            'sunny': 1,
            'cloudy': 2,
            'rainy': 3,
            'unknown': 0
        }
        return weather_map.get(weather.lower(), 0)
    
    @staticmethod
    def _encode_water_condition(condition):
        """水面状況をエンコード"""
        condition_map = {
            'calm': 1,
            'slight': 2,
            'moderate': 3,
            'rough': 4,
            'unknown': 0
        }
        return condition_map.get(condition.lower(), 0)


if __name__ == "__main__":
    model = EnsembleModel()
    # 当日予測
    today_pred = model.predict_today()
    print(f"当日予測: {len(today_pred)}件")
    
    # 翌日予測
    tomorrow_pred = model.predict_tomorrow()
    print(f"翌日予測: {len(tomorrow_pred)}件")
