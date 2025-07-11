
from sklearn.multioutput import MultiOutputRegressor
from joblib import parallel_backend
import numpy as np
from lightgbm import LGBMRegressor
from utils.AI.ensemble_forecaster.optimize import shuffle_weekly_blocks_keep_index

class LGBMModel:
    
    model_type = 'ML' # 머신러닝 모델
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train, **kwargs):
        params = {
            'n_estimators': 500,
            'learning_rate': 0.01,
            'num_leaves': 31,
            'objective': 'regression',
            'verbose': -1
        }
        if hasattr(self.config, 'lgbm_params'):
            params= {**self.config.lgbm_params}

        model = MultiOutputRegressor(LGBMRegressor(**params))
        model.fit(X_train, y_train)
        return model

    def build_best_model(self, X_train, y_train, best_params, sample_weight=None):
        model = MultiOutputRegressor(LGBMRegressor(**{**self.config.lgbm_params, **best_params}))
        X_train_shuffled, y_train_shuffled = shuffle_weekly_blocks_keep_index(X_train, y_train, week_len=self.config.input_seq_len )
        if sample_weight is not None:
            model.fit(X_train_shuffled, y_train_shuffled, sample_weight=sample_weight)
        else:
            model.fit(X_train_shuffled, y_train_shuffled)
        return model