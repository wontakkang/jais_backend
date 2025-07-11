from sklearn.multioutput import MultiOutputRegressor
from sklearn.ensemble import GradientBoostingRegressor

from utils.AI.ensemble_forecaster.optimize import shuffle_weekly_blocks_keep_index

class GBMModel:
    model_type = 'ensemble_ML'  # 머신러닝 모델
    def __init__(self, config):
        self.config = config

    def build(self, X_train=None, y_train=None, sample_weight=None, **kwargs):
        params = {
            'n_estimators': 500,
            'learning_rate': 0.01,
            'max_depth': 3,
            'loss': 'squared_error'
        }
        if hasattr(self.config, 'gbm_params'):
            params = {**params, **self.config.gbm_params}
        params.update(kwargs)  # 튜닝용 best_params도 적용

        model = MultiOutputRegressor(GradientBoostingRegressor(**params))

        # X_train, y_train이 있으면 fit까지
        if X_train is not None and y_train is not None:
            if sample_weight is not None:
                model.fit(X_train, y_train, sample_weight=sample_weight)
            else:
                model.fit(X_train, y_train)
        return model

    def build_best_model(self, X_train, y_train, best_params, sample_weight=None):
        return self.build(X_train, y_train, sample_weight, **best_params)
    