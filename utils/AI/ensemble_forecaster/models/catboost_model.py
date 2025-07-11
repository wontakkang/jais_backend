# boosting_models.py
from sklearn.multioutput import MultiOutputRegressor
from joblib import parallel_backend
import numpy as np
from catboost import CatBoostRegressor
from utils.AI.ensemble_forecaster.optimize import shuffle_weekly_blocks_keep_index

class CatBoostModel:
    model_type = 'ML' # 머신러닝 모델
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train, **kwargs):
        params = {
            'iterations': 500,
            'learning_rate': 0.01,
            'depth': 6,
            'loss_function': 'MultiRMSE',
            'verbose': 0,
        }
        if hasattr(self.config, 'catboost_params'):
            params= {**self.config.catboost_params}
        model = MultiOutputRegressor(CatBoostRegressor(**params))
        model.fit(X_train, y_train)
        return model

    def build_best_model(self, X_train, y_train, best_params, sample_weight=None):
        merge = {**self.config.catboost_params, **best_params}
        model = MultiOutputRegressor(CatBoostRegressor(**{**self.config.catboost_params, **best_params}))
        X_train_shuffled, y_train_shuffled = shuffle_weekly_blocks_keep_index(X_train, y_train, week_len=self.config.input_seq_len)
        if sample_weight is not None:
            model.fit(X_train_shuffled, y_train_shuffled, sample_weight=sample_weight)
        else:
            model.fit(X_train_shuffled, y_train_shuffled)
        return model