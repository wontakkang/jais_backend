# config.py
"""
모델 기본 설정값 관리
- 모델별 기본 파라미터
- 모델별 하이퍼파라미터 튜닝 범위
- 데이터 컬럼 및 경로 설정
"""

# ================================
# 0. 임시 settings (Jupyter Notebook 전용)
# ================================

# AI Logger 설정
import numpy as np
from utils.AI.ensemble_forecaster.logger import setup_logger
from utils.config import settings
import os
ensembleForecaster_logger = setup_logger(name="EnsembleForecaster_logger", log_file=f"{settings.LOG_DIR}/EnsembleForecaster.log")

class DefaultConfig:
    # 예측 모델에 적용될 샘플 가중치 함수
    def sample_weight_func(self, X, y, scale=2.0):
        """
        예측 모델 학습 시 사용할 샘플 가중치 생성 함수.

        Parameters:
            X (array-like): 입력 데이터 (사용하지 않음)
            y (array-like): 타깃 벡터
            scale (float): 가중치 상한 (1.0 ~ scale 사이 값으로 생성)

        Returns:
            np.ndarray: 각 샘플에 대한 가중치 벡터
        """
        weights = np.random.uniform(1.0, scale, len(y))

        # 가중치 통계 로깅
        ensembleForecaster_logger.info(f"[sample_weight_func] 샘플 수: {len(y)},  가중치 범위: min={weights.min():.4f}, max={weights.max():.4f},  가중치 평균: mean={weights.mean():.4f}, 표준편차: std={weights.std():.4f}")

        return weights
    
    def __init__(self):
        
        # 전처리 관련 설정
        self.row_size = '5m'                            # 데이터 샘플링 주기
        self.ref_interval = 5                          # 데이터 샘플링 주기
        self.step_size = int(60/self.ref_interval) * 24    # step size
        self.input_seq_len = self.step_size * 7         # 학습 데이터 길이
        self.output_seq_len = self.step_size * 3        # 예측 데이터 길이
        self.cpu_count = int(os.cpu_count()*0.8)  # CPU 코어 수 (80% 사용)

        # 데이터 관련 설정, *settings.NETWORK.keys()
        self.tag_datetime = 'READ_DATETIME'
        self.target_columns = [*settings.PWR_WM.keys()]
        self.feature_columns = [*settings.FEATURES.keys()]
        self.target_labels = {**settings.PWR_WM}
        self.filtered_columns = []
        
        # 머신 러닝 모델 기본 파라미터
        self.catboost_params = self._catboost_default()
        self.lgbm_params = self._lgbm_default()
        self.xgb_params = self._xgboost_default()
        
        # 앙상블 머신 러닝 모델 모델 기본 파라미터
        self.gradientboost_params = self._gradientboost_default()
        self.ml_model_list = ["lgbm", "catboost", "xgboost", "gbm"]
        self.class_weight = 'balanced'
    
        # 딥 러닝 모델 기본 파라미터
        self.cnn_params = self._cnn_default()
        self.lstm_params = self._lstm_default()
        self.cnn_lstm_params = self._cnn_lstm_default()
        self.tft_params = self._tft_default()
        self.cnn_tft_params = self._cnn_tft_default()
        self.patchtst_params = self._patchtst_default()
        self.informer_params = self._informer_default()
        
        # 재학습 평가지표 리스트
        self.retrain_metrics = ['mse', 'mae', 'smape', 'r2']  # 재학습 평가지표 리스트 추가

        # 하이퍼파라미터 튜닝 범위
        self.hyperparameter_grids = self._hyperparameter_defaults()

        # 저장 경로 설정
        self.base_path = settings.BASE_PATH
        self.model_save_path = f'{self.base_path}model/'
        self.scaler_save_path = f'{self.base_path}scaler/'
        self.report_save_path = f'{self.base_path}report/'
        self.hyperparameters_save_path = f'{self.base_path}hyperparameters/'
        self.dataPattern_save_path = f'{self.base_path}dataPatterns/'
        self.features_save_path = f'{self.base_path}fitered_features/'

        # Optuna 파라미터 설정
        self.optuna_neighborhood_ratio = {
            'catboost': 1.0,
            'lgbm': 1.5,
            'xgboost': 1.0,
            'tft': 2.0,
            'cnntft': 2.0,
            'patchtst': 2.0,
            'informer': 2.0,
            'lstm': 2.0,
            'cnnlstm': 2.0,
            'gbm': 1.0,
        }
        self.optuna_neighborhood_params = {
            'catboost': ['learning_rate', 'depth', 'l2_leaf_reg', 'bagging_temperature', 'random_strength', 'leaf_estimation_iterations'],
            'lgbm': ['learning_rate', 'num_leaves', 'max_depth', 'min_data_in_leaf', 'feature_fraction', 'bagging_fraction', 'lambda_l1', 'lambda_l2'],
            'xgboost': ['learning_rate', 'max_depth', 'min_child_weight', 'subsample', 'colsample_bytree', 'gamma', 'lambda', 'alpha'],
            'tft': ['num_heads', 'hidden_size', 'dropout_rate', 'learning_rate'],
            'cnntft': ['conv_filters', 'attention_heads', 'transformer_units', 'hidden_units', 'dropout_rate', 'learning_rate'],
            'patchtst': ['hidden_units', 'd_model', 'patch_len', 'stride', 'learning_rate'],
            'informer': ['hidden_units', 'd_model', 'n_heads', 'dropout_rate', 'factor', 'learning_rate'],
            'lstm': ['hidden_units', 'num_layers', 'lstm_units', 'dropout_rate', 'learning_rate'],
            'cnnlstm': ['conv_filters', 'lstm_units', 'hidden_units', 'dropout_rate', 'learning_rate'],
            'gbm': ['learning_rate', 'n_estimators', 'max_depth', 'min_samples_split', 'min_samples_leaf', 'subsample'],
        }

    def _cnn_default(self):
        return {
            'conv_filters': 128,         # Conv1D 필터 수
            'hidden_units': 512,          # Dense 유닛 수
            'learning_rate': 1e-3,        # 학습률
            'loss': 'mse'                 # 손실 함수
        }
    def _lstm_default(self):
        return {
            'lstm_units': 64,
            'dropout_rate': 0.2,
            'learning_rate': 0.001,
            'optimizer': 'adam',
            'loss': 'mse',
            'metrics': ['mae'],
        }
    def _cnn_lstm_default(self):
        return {
            'conv_filters': 64,
            'lstm_units': 64,
            'hidden_units': 128,
            'dropout_rate': 0.2,
            'learning_rate': 1e-3,
            'loss': 'mse'
        }
    def _tft_default(self):
        return {
            'num_heads': 4,
            'hidden_size': 64,
            'dropout_rate': 0.1,
            'learning_rate': 0.001,
            'optimizer': 'adam',
            'loss': 'mse',
            'metrics': ['mae'],
        }
    def _cnn_tft_default(self):
        return {
            'conv_filters': 64,         # Conv1D 필터 개수
            'attention_heads': 4,       # MultiHead Attention 헤드 수
            'transformer_units': 128,   # Transformer FeedForward 층 유닛 수
            'hidden_units': 128,        # Dense 층 유닛 수
            'dropout_rate': 0.1,        # 드롭아웃 비율
            'learning_rate': 1e-3,      # 학습률
            'loss': 'mse'               # 손실 함수 (MSE 또는 Huber)
        }

    # 🔹 PatchTST 기본 설정
    def _patchtst_default(self):
        return {
            'd_model': 128,
            'n_heads': 4,
            'patch_len': 16,
            'stride': 8,
            'dropout_rate': 0.2,
            'learning_rate': 0.001,
            'optimizer': 'adam',
            'loss': 'mse',
            'metrics': ['mae'],
        }

    # 🔹 Informer 기본 설정
    def _informer_default(self):
        return {
            'd_model': 128,
            'n_heads': 4,
            'dropout_rate': 0.1,
            'factor': 5,              # Informer-specific
            'learning_rate': 0.001,
            'optimizer': 'adam',
            'loss': 'mse',
            'metrics': ['mae'],
        }

    def _catboost_default(self):
        return {
            'loss_function': "MultiRMSE",
            'eval_metric': "MultiRMSE",
            'thread_count': 12,
            'random_seed': 42,
            'grow_policy': 'Lossguide',
            'early_stopping_rounds': 50,
            'verbose': 0,
        }

    def _lgbm_default(self):
        return {
            # 'boosting_type': "gbdt",
            # 'device': "gpu",
            'n_jobs': self.cpu_count,
            'max_bin': 255,
            'verbosity': -1,
            'min_gain_to_split': 0.0,      # 이득 조건 완화
        }

    def _xgboost_default(self):
        return {
            'verbosity': 0,  # 로그 출력 수준. 0: 없음, 1: 정보, 2: 경고, 3: 디버깅
            # "tree_method": "hist",
            # "device": "cuda",
            # 'tree_method': 'hist',  # CPU 스레드 개수 설정 (8코어 사용)
            'n_jobs': self.cpu_count,
            # 모델 학습 관련
            "objective": "reg:squarederror",  # 회귀 문제
            "eval_metric": ["rmse", "mae"],  # 회귀 성능 평가 지표
            # "eval_metric": ["logloss", "auc"],  # 분류 성능 평가 지표
        }

    def _gradientboost_default(self):
        return {
            'random_state': 42,
        }

    def _hyperparameter_defaults(self):
        return {
            'CatboostModel': {
                'objective': ['MultiRMSE'],
                'feature_border_type': ['Median', 'Uniform'],
                'grow_policy': ['SymmetricTree', 'Depthwise'],
                'depth': list(range(3, 13)),
                'learning_rate': [0.0025, 0.005, 0.01, 0.02, 0.025, 0.035, 0.05, 0.075, 0.1, 0.15, 0.2],
                'n_estimators': list(range(300, 1600, 100)),
                'bagging_temperature': [0.01, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0],
                'random_strength': [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0],
                'l2_leaf_reg': [0.05, 0.1, 0.3, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0],
                'border_count': [32, 64, 128, 255],
                'bootstrap_type': ['Bayesian'],
                'leaf_estimation_method': ['Newton', 'Gradient'],
                'leaf_estimation_iterations': [1, 3, 5, 10, 15, 20],
            },
            'LgbmModel': {
                'task': ['train'],
                'tree_learner': ['feature'],
                'objective': ['regression', 'huber', 'fair', 'poisson'],
                'metric': ['rmse', 'mape', 'mae'],
                'num_leaves': [15, 25, 31, 40, 50, 75, 100, 125, 150],
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3],
                'n_estimators': list(range(300, 1600, 100)),
                'max_depth': [-1, 3, 4, 5, 6, 7, 8, 9, 10],
                'min_data_in_leaf': [5, 10, 15, 20, 30, 50],
                'min_child_samples': [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                'feature_fraction': [0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                'bagging_fraction': [0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                'bagging_freq': [1, 3, 5],
                'lambda_l1': [0.0, 0.01, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0],
                'lambda_l2': [0.0, 0.01, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0],
                'colsample_bynode': [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                'importance_type': ["gain"],
            },
            'XgboostModel': {
                'max_depth': list(range(3, 13)),
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2],
                'n_estimators': list(range(250, 1600, 100)),
                'min_child_weight': [1, 2, 3, 5, 7, 10],
                'subsample': [0.3, 0.5, 0.7, 0.8, 0.9, 1.0],
                'colsample_bytree': [0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                'gamma': [0, 0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],
                'lambda': [0, 0.01, 0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0],
                'alpha': [0, 0.01, 0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0],
            },
            'TFTModel': {
                'num_heads': [2, 4, 6, 8],
                'hidden_size': [32, 64, 128],
                'dropout_rate': [0.1, 0.2, 0.3],
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2],
                'loss': ['mse', 'huber'],
            },
            'CNNTFTModel': {
                'conv_filters': [32, 64, 128],
                'attention_heads': [2, 4, 8],
                'transformer_units': [64, 128, 256],
                'hidden_units': [64, 128, 256],
                'dropout_rate': [0.0, 0.1, 0.2, 0.3],
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2],
                'loss': ['mse', 'huber']
            },
            'PatchTSTModel': {
                'hidden_units': [32, 64, 128, 256, 512],
                'd_model': [64, 128, 256],
                'patch_len': [8, 16, 32],
                'stride': [4, 8, 16],
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2],
                'loss': ['mse', 'huber'],
            },
            'InformerModel': {
                'hidden_units': [32, 64, 128, 256, 512],
                'd_model': [64, 128, 256],
                'n_heads': [2, 4, 8],
                'dropout_rate': [0.1, 0.2],
                'factor': [3, 5, 7],  # Informer-specific
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2],
                'loss': ['mse', 'huber'],
            },
            'LSTMModel': {
                'hidden_units': [32, 64, 128, 256, 512],
                'num_layers': [1, 2, 3],
                'lstm_units': [32, 64, 128, 256],
                'dropout_rate': [0.0, 0.1, 0.3, 0.5],
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2],
                'loss': ['mse', 'huber'],
            },
            'CNNLSTMModel': {
                'conv_filters': [32, 64, 128],
                'lstm_units': [32, 64, 128, 256],
                'hidden_units': [64, 128, 256],
                'dropout_rate': [0.0, 0.1, 0.2, 0.3],
                'learning_rate': [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2],
                'loss': ['mse', 'huber']
            },
            'GbmModel': {
                'loss': ['squared_error', 'absolute_error', 'huber', 'quantile'],  # 손실 함수 선택
                'learning_rate': [0.0025, 0.005, 0.0075, 0.01, 0.015, 0.025, 0.035, 0.05, 0.075, 0.1, 0.125, 0.15, 0.175, 0.2, 0.25],  # 학습률 조정
                'n_estimators': [500, 600, 700, 800, 900, 950, 1000, 1100, 1200, 1300, 1400, 1500],  # 부스팅 반복 횟수
                'subsample': [0.3, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0],  # 배깅 샘플링 비율
                'criterion': ['friedman_mse', 'squared_error'],  # 분할 기준
                'max_depth': [3, 4, 5, 6, 7, 8, 9, 10, 12],  # 트리 깊이
                'min_samples_split': [2, 5, 10, 15, 20, 25, 30, 50],  # 노드 분할 최소 샘플 수
                'min_samples_leaf': [1, 3, 5, 10, 15, 20, 30],  # 리프 노드 최소 샘플 수
                'max_features': ['sqrt', 'log2', None, 0.5, 0.7, 0.9], # 피처 선택 방식 (트리마다 사용할 변수 개수 결정)
                'alpha': [0.5, 0.6, 0.7, 0.75, 0.85, 0.9, 0.95],  # Huber & Quantile 손실 함수 조정 (Huber/Quantile 사용 시)
                'random_state': [42],  # 재현성을 위한 랜덤 시드
                "ccp_alpha": [0.0, 0.00001, 0.0001, 0.001, 0.01],
            }
        }

    def load_hyperparameter_grids_from_file(self, json_path):
        """
        지정한 json 파일로부터 hyperparameter_grids 값을 덮어쓴다.
        """
        if not os.path.exists(json_path):
            ensembleForecaster_logger.error(f"Hyperparameter grid file not found: {json_path}")
            return
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            for key, value in json.load(f).items():
                # key에 'Model'이 포함되어 있으면 그대로, 없으면 'Model'을 붙여서 key 생성
                if 'Model' in key:
                    new_key = key
                else:
                    new_key = f"{key}Model"
                if key in self.hyperparameter_grids:
                    self.hyperparameter_grids[new_key].update(value)
                else:
                    self.hyperparameter_grids[new_key] = value

# 인스턴스 생성
defaultConfig = DefaultConfig()
