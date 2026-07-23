"""
データ処理ユーティリティ
予測データの前処理、正規化、キャッシュ機能
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DataPreprocessor:
    """データ前処理クラス"""
    
    @staticmethod
    def normalize_features(features: Dict[str, float]) -> Dict[str, float]:
        """特徴量を正規化（0-1範囲）"""
        try:
            if not features:
                return {}
            
            normalized = {}
            for key, value in features.items():
                if isinstance(value, (int, float)):
                    # 簡易的な正規化（0-1範囲）
                    if value < 0:
                        normalized[key] = 0.0
                    elif value > 1:
                        normalized[key] = 1.0
                    else:
                        normalized[key] = float(value)
                else:
                    normalized[key] = value
            
            return normalized
        except Exception as e:
            logger.error(f"特徴量正規化エラー: {e}")
            return features
    
    @staticmethod
    def validate_prediction(prediction: Dict[str, Any]) -> bool:
        """予測データを検証"""
        required_fields = ['date', 'place', 'race_number', 'prediction', 'confidence']
        
        for field in required_fields:
            if field not in prediction:
                logger.warning(f"必須フィールドが見つかりません: {field}")
                return False
        
        # 信頼度は0-1の範囲か確認
        if not 0 <= prediction['confidence'] <= 1:
            logger.warning(f"信頼度が範囲外です: {prediction['confidence']}")
            return False
        
        return True
    
    @staticmethod
    def aggregate_predictions(predictions: List[Dict]) -> Dict[str, Any]:
        """複数の予測を集約"""
        if not predictions:
            return {}
        
        total_predictions = len(predictions)
        high_confidence = sum(1 for p in predictions if p.get('confidence', 0) >= 0.7)
        avg_confidence = sum(p.get('confidence', 0) for p in predictions) / total_predictions
        
        return {
            'total_predictions': total_predictions,
            'high_confidence_count': high_confidence,
            'average_confidence': avg_confidence,
            'success_rate': (high_confidence / total_predictions * 100) if total_predictions > 0 else 0
        }


class CacheManager:
    """キャッシュ管理クラス"""
    
    CACHE_DIR = ".cache"
    
    def __init__(self):
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)
    
    def get(self, key: str) -> Any:
        """キャッシュから値を取得"""
        try:
            cache_file = os.path.join(self.CACHE_DIR, f"{key}.json")
            
            if not os.path.exists(cache_file):
                return None
            
            # キャッシュの有効期限を確認（1時間）
            mtime = os.path.getmtime(cache_file)
            if datetime.now() - datetime.fromtimestamp(mtime) > timedelta(hours=1):
                os.remove(cache_file)
                return None
            
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"キャッシュ取得エラー: {e}")
            return None
    
    def set(self, key: str, value: Any) -> bool:
        """キャッシュに値を保存"""
        try:
            cache_file = os.path.join(self.CACHE_DIR, f"{key}.json")
            
            with open(cache_file, 'w') as f:
                json.dump(value, f)
            
            logger.debug(f"キャッシュを保存しました: {key}")
            return True
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}")
            return False
    
    def clear(self) -> bool:
        """すべてのキャッシュをクリア"""
        try:
            for file in os.listdir(self.CACHE_DIR):
                if file.endswith('.json'):
                    os.remove(os.path.join(self.CACHE_DIR, file))
            logger.info("キャッシュをクリアしました")
            return True
        except Exception as e:
            logger.error(f"キャッシュクリアエラー: {e}")
            return False


if __name__ == "__main__":
    # テスト
    preprocessor = DataPreprocessor()
    cache_manager = CacheManager()
    
    # 特徴量正規化のテスト
    features = {'weather': 1.5, 'water': 0.5}
    normalized = preprocessor.normalize_features(features)
    print(f"正規化前: {features}")
    print(f"正規化後: {normalized}")
    
    # キャッシュのテスト
    test_data = {'test': 'data'}
    cache_manager.set('test_key', test_data)
    retrieved = cache_manager.get('test_key')
    print(f"キャッシュ保存・取得テスト: {retrieved}")
