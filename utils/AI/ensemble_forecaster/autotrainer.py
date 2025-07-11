# autotrainer.py
import json
import pandas as pd
import numpy as np
import os
from utils.config import settings
from utils.AI.ensemble_forecaster.utilities import adjusted_r2, calculate_vif, coefficient_of_variation_rmse, convert_numpy_types, evaluate_performance, generate_final_conclusion, get_latest_trial_path, get_next_trial_path, mean_absolute_percentage_error, nmbe, normalized_mean_bias_error, rmse, symmetric_mean_absolute_percentage_error, weighted_mean_absolute_percentage_error
from utils.AI.ensemble_forecaster.optimize import *
from utils.AI.ensemble_forecaster.ensemble_forecaster import EnsembleForecaster
from utils.AI.ensemble_forecaster.feature_engineering import (
    apply_scaling, 
    detect_time_series_patterns,
    generate_aggregation_features, 
    generate_autocorrelation_features, 
    generate_lag_features, 
    handle_missing_values, 
    optimize_outlier_removal,
    make_sensor_column_map,
    add_discomfort_features,
)
"""
AutoFeature + AutoTrainer
- 데이터 자동 전처리
- 모델 자동 튜닝, 학습, 저장
- KFold/TimeSeriesSplit 지원
- 이상치 기반 라벨링 지원
- 성능 평가(evaluate_models) 통합
"""

class AutoFeature:
    """ 입력 데이터 자동 전처리 + 특징 생성 + 최적화 + 이상치 라벨링 """
    def __init__(self, config, logger, scaler_mode="per_feature"):
        self.config = config
        self.logger = logger
        self.scaler_mode = scaler_mode

    def full_preprocessing(self, raw_data, label_outliers=False, mode='train'):
        """ 전체 전처리: 결측치 처리, 이상치 제거, 특징 생성, 스케일링, (선택) 이상치 라벨 생성 """

        df = raw_data.copy()
        self.logger.info(f"전처리 시작...{df.index.min()}, {df.index.max()}")
        expanded_features = self.config.feature_columns.copy()
        # 1. 결측치 최적화
        if self.config.data_patterns.get('has_missing_values', False):
            df = handle_missing_values(df, method="ffill")
            df = handle_missing_values(df, method="bfill")

        # 2. 이상치 최적화
        if self.config.data_patterns.get('is_noisy', False):
            for method in settings.removal_methods_list:
                df_no_outliers = optimize_outlier_removal(df, method=method, target_columns=self.config.target_columns)
        else:
            df_no_outliers = df

        # Feature Engineering
        # 목적: 과거 데이터를 현재 예측에 활용, 탐지된 Lag 정보를 반영하여 Lag 변수만 생성
        df_expanded, added_cols = generate_lag_features(df_no_outliers, self.config.target_columns, self.config.data_patterns)
        expanded_features.extend(added_cols)
        
        # 집계 유형 추천 정보를 활용하여 집계 변수를 생성하는 함수.
        df_expanded, added_cols = generate_aggregation_features(df_expanded, self.config.target_columns, self.config.data_patterns)
        expanded_features.extend(added_cols)
        
        # 목적: 특정 시간 단위(일, 주, 월)에서 반복되는 패턴을 학습
        df_expanded, added_cols = generate_autocorrelation_features(df_expanded, self.config.target_columns, self.config.data_patterns)
        expanded_features.extend(added_cols)
        
        # 일출/일몰 기반 주기적 특징 추가
        df_expanded, added_cols = generate_sun_based_cyclic_features(df_expanded, settings.LAT, settings.LNG)
        expanded_features.extend(added_cols)
        
        # 피크 감지 결과를 활용하여 추가적인 피크 관련 변수를 생성하는 함수.
        df_expanded, added_cols = add_peak_features(df_expanded, self.config.target_columns, self.config.data_patterns, ref_interval=self.config.ref_interval)
        
        # AWS/IARAW 실내외 환경 센서 데이터 기반 특징 생성
        aws_columns, iaraw_columns = make_sensor_column_map(df_expanded, settings)
        df_expanded, added_cols = add_discomfort_features(df_expanded, aws_columns, iaraw_columns)
        expanded_features.extend(added_cols)
        
        if mode in ["train"]:
            # 4. 특징, 타겟 분리
            y_targets = df_expanded[self.config.target_columns]
            # 튜닝 전에 분산이 낮은 피처를 제거
            X_train_reduced, _, self.config.filtered_columns, filtering_report = feature_filter_auto(
                df_expanded[expanded_features], y_targets, keep_ratio=0.8, auto_tune=True, use_cov_corr=True, return_report=True
            )
            removed_cols = [col for col in df_expanded[expanded_features].columns if col not in self.config.filtered_columns]
            self.logger.info("제거된 피처 목록: %s", removed_cols)
            self.save_data_pattern(filtering_report, base_dir=self.config.report_save_path, filename="filtering_report.json")
            # 이상치 라벨링 (선택)
            if label_outliers:
                self.logger.info("이상치 기반 라벨링 수행...")
                y_labels = self._generate_outlier_labels(y_targets)
            else:
                y_labels = y_targets
                
            # 데이터셋을 7일 테스트 셋과 7일*n 묶음의 훈련 셋으로 분리
            test_size = self.config.input_seq_len  # 7일 (시간 단위로 계산)
            train_size = len(X_train_reduced) - test_size  # 전체 길이에서 테스트 크기 제외
            batch_size = (train_size / self.config.input_seq_len)
            if train_size % self.config.input_seq_len != 0:
                train_size = (train_size // self.config.input_seq_len) * self.config.input_seq_len  # 7일*n 묶음으로 조정
            X_train, X_test = X_train_reduced.iloc[-train_size-test_size:-test_size], X_train_reduced.iloc[-test_size:]
            y_train, y_test = y_labels.iloc[-train_size-test_size:-test_size], y_labels.iloc[-test_size:]
            self.preprocess_data = {
                "X_train": X_train,
                "X_test": X_test,
                "y_train": y_train,
                "y_test": y_test,
                "batch_size": batch_size,
            }
        else:
            # Scaler 불러오기
            self.scalers = load_scalers(base_dir=self.config.scaler_save_path)
            # 기존 학습모델의 특징 불러오기
            self.config.filtered_columns = self.load_data_pattern(base_dir=self.config.features_save_path, filename="filtered_features.json")
            X_features = df_expanded[self.config.filtered_columns]
            y_targets = df_expanded[self.config.target_columns]
            now = df_expanded.index.min() + pd.Timedelta(days=1)
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            X_features = X_features[start_time:]
            y_targets = y_targets[start_time:]
            self.preprocess_data = {
                "X_test": X_features,
                "y_test": y_targets,
            }            
            
        return self.preprocess_data

    def _generate_outlier_labels(self, y_data, threshold=3.0):
        """ 이상치 기반 라벨 생성 (Z-score 기반) """
        labels = pd.DataFrame(index=y_data.index)
        for col in y_data.columns:
            series = y_data[col]
            mean = series.mean()
            std = series.std()
            z_scores = (series - mean) / std
            labels[col + "_outlier_label"] = (np.abs(z_scores) > threshold).astype(int)
        return labels
        
    def fit_transform(self, X, mode="per_feature"):
        """ 
        훈련 데이터 스케일링 (Batch 데이터용)
        
        Args:
            X (np.array): 입력 데이터 (2D 또는 3D 가능)
            mode (str): "per_feature" (특징별 다른 스케일러) 또는 "global" (전체 같은 스케일러)
        
        Returns:
            np.array: 스케일링된 데이터 (3D 형태 유지)
        """
        # 1. 컬럼과 인덱스를 백업해두고
        columns = X.columns
        index = X.index
        # 0. 결측치 -> 0으로 대체
        X = np.nan_to_num(X)
        # ✅ bool → float 변환 추가
        if np.issubdtype(X.dtype, np.bool_):
            X = X.astype(np.float32)
        else:
            # 혼합된 경우에도 강제 변환
            X = np.where(X == False, 0.0, X)
            X = np.where(X == True, 1.0, X)
            X = X.astype(np.float32)
        # ⬅️ 다시 DataFrame으로 복원
        df = pd.DataFrame(X, columns=columns, index=index)
        # apply_scaling 함수 사용
        scaled_df, scaler_dict, log_needed_dict, expanded_features = apply_scaling(
            df,
            target_columns=self.config.filtered_columns,
            mode=mode
        )

        # ✅ Scaler 저장
        save_scalers(scaler_dict, base_dir=self.config.scaler_save_path)

        # 필요한 정보 저장
        self.scalers = scaler_dict
        self.log_needed = log_needed_dict
        self.expanded_features = expanded_features

        return scaled_df

    def transform(self, X):
        """
        새로운 데이터에 기존 학습된 Scaler를 적용하는 함수.

        Parameters:
            df_new (pd.DataFrame): 변환할 새로운 데이터프레임
            scaler_dict (dict): 기존 학습된 Scaler 객체 딕셔너리

        Returns:
            pd.DataFrame: 변환된 데이터프레임
        """
        transformed_df = X.copy()
        if self.scalers:
            # transformed_df = X.copy() # Ensure transformed_df is a copy if not already.
            for col in self.scalers: # Assuming self.scalers is a dict {col_name: scaler_object}
                scaler = self.scalers[col]
                try:
                    if col in X.columns: # Check if the column exists in the input DataFrame X
                        transformed_df[col] = scaler.transform(X[[col]]) # Original line 194
                    else:
                        # Log a warning if a column expected by a scaler is missing.
                        ensembleForecaster_logger.warning(
                            f"Column '{col}' was expected by a scaler but was not found in the input DataFrame. "
                            f"Skipping scaling for this column. This may affect model performance if the column is critical."
                        )
                except Exception as e:
                    # Log an error if scaling fails for a column.
                    ensembleForecaster_logger.error(
                        f"Error scaling column '{col}': {e}. "
                        f"Ensure the scaler is compatible with the data type and shape of the input DataFrame."
                    )
        
        # Apply feature selection if a selector is fitted
        if hasattr(self, 'selector') and self.selector is not None:
            transformed_df = self.selector.transform(transformed_df)

        return transformed_df
    
    def detect_patterns(self, raw_data, target_columns, max_lag=30, ref_interval=5, peak_threshold=2.0):
        """ 시계열 데이터 패턴 탐지 """
        return detect_time_series_patterns(
            raw_data, target_columns, max_lag=max_lag, ref_interval=ref_interval, peak_threshold=peak_threshold
        )

    # -------------------------------
    # 데이터패턴 저장 및 로딩
    # -------------------------------

    def save_data_pattern(self, data_pattern: dict, base_dir="models", trial_num=None, filename="dataPattern.json"):
        """
        데이터 패턴 정보 저장 함수

        Args:
            data_pattern (dict): 저장할 데이터 패턴 정보 (예: {"input_window": 24, "features": [...], ...})
            base_dir (str): 기본 저장 경로 (default: "models")
            trial_num (int, optional): 저장할 trial 번호
            filename (str): 저장할 파일 이름 (default: "dataPattern.json")
        """
        data_pattern = convert_numpy_types(data_pattern)
        # 데이터 패턴을 JSON 직렬화 가능한 기본 타입으로 변환
        save_path = get_next_trial_path(base_dir, trial_num=trial_num)
        os.makedirs(save_path, exist_ok=True)

        file_path = os.path.join(save_path, filename)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data_pattern, f, ensure_ascii=False, indent=4, default=str)
            self.logger.info(f"✅ 데이터 패턴 저장 완료: {file_path}")
        except Exception as e:
            self.logger.info(f"❌ 데이터 패턴 저장 실패: {e}")

    def load_data_pattern(self, base_dir="models", trial_num=None, filename="dataPattern.json"):
        """
        저장된 데이터 패턴 정보 로딩 함수

        Args:
            base_dir (str): 저장 경로 기본값 (default: "models")
            trial_num (int, optional): 불러올 trial 번호
            filename (str): 파일 이름 (default: "dataPattern.json")

        Returns:
            dict: 로딩된 데이터 패턴 정보
        """
        load_path = get_latest_trial_path(base_dir, trial_num)
        file_path = os.path.join(load_path, filename)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data_pattern = json.load(f)
            self.logger.info(f"✅ 데이터 패턴 로딩 완료: {file_path}")
            return data_pattern
        except Exception as e:
            self.logger.info(f"❌ 데이터 패턴 로딩 실패: {e}")
            return None     
            
        
class AutoTrainer:
    """ 전체 자동 학습 파이프라인 """
    def __init__(self, forecaster: EnsembleForecaster, auto_feature=None):
        self.forecaster = forecaster
        self.auto_feature = auto_feature

    def run(self, processed_data, model_list, max_trials=10, epochs=50, batch_size=8, mode="per_feature"):
        """
        전체 AutoFeature + AutoTrain 수행
        """
        self.forecaster.logger.info("[AutoTrainer] Start AutoFeature...")
        self.auto_feature = AutoFeature(config=self.forecaster.config, logger=self.forecaster.logger)
        fited_X_train = self.auto_feature.fit_transform(processed_data['X_train'], mode="per_feature")
        fited_X_test = self.auto_feature.transform(processed_data['X_test'])
        if epochs == 0:
            self._ML_train_once(fited_X_train, processed_data['y_train'], fited_X_test, processed_data['y_test'], model_list, max_trials, epochs, batch_size)
        else:
            self._DL_train_once(fited_X_train, processed_data['y_train'], fited_X_test, processed_data['y_test'], model_list, max_trials, epochs, batch_size)
        self.forecaster.logger.info("[AutoTrainer] Training and Saving Complete.")

    def _DL_train_once(self, X_train, y_train, X_val, y_val, model_list, max_trials, epochs, batch_size):
        """ 하나의 train/validation 셋에 대해 학습 및 튜닝 """
        self.forecaster.auto_tune(
            model_list, 
            X_train, 
            y_train, 
            max_trials=max_trials, 
            batch_size=batch_size, 
            epochs=epochs
        )
        self.forecaster._DL_auto_ensemble(X_val, y_val)
        self.forecaster.save_all_models(base_dir=self.forecaster.config.model_save_path)

    def _ML_train_once(self, X_train, y_train, X_val, y_val, model_list, max_trials, epochs, batch_size, mode="train"):
        """ 하나의 train/validation 셋에 대해 학습 및 튜닝 """
        self.forecaster.auto_tune(
            model_list, 
            X_train, 
            y_train, 
            max_trials=max_trials, 
            batch_size=batch_size, 
            epochs=epochs,
        )
        # 모델 저장
        self.forecaster.save_all_models(base_dir=self.forecaster.config.model_save_path)

    def predict(self, X_test):
        """ AutoFeature 적용 후 예측 """

        # AutoFeature 스케일링
        X_test = self.auto_feature.transform(X_test)

        # Ensemble 예측
        preds = self.forecaster.ensemble_predict(
            list(self.forecaster.tuned_models.keys()), 
            X_test,
            weights=self.forecaster.ensemble_weights
        )
        return preds

    def ml_predict(self, X_test):
        """ AutoFeature 적용 후 예측 """
        # AutoFeature 스케일링
        scaled_X_test = self.auto_feature.transform(X_test)
        self.forecaster.load_all_models(base_dir=self.forecaster.config.model_save_path)
        
        train_predictions = []
        stacked_predictions = []

        # 하나씩 predict 하고 append
        for name, model in self.forecaster.models.items():
            if name not in ['final_ensemble', 'best_gbm']:
                pred = model.predict(scaled_X_test)
                train_predictions.append(pred)
        self.base_predictions = train_predictions
        # 리스트를 (n_samples, n_models) shape로 변환
        stacked_predictions = np.hstack(train_predictions)
        y_pred = self.forecaster.models['best_gbm'].predict(stacked_predictions)
        # Ensemble 예측
        return y_pred

    def ml_evaluate_models(self, y_true, y_preds_base, y_pred_ensemble, column_names=None, mode="all"):
        """
        베이스 모델들과 앙상블 모델의 성능을 평가하는 함수 (다차원 데이터 지원)
        """
        if mode == "live":
            now = pd.Timestamp.now()
            end_time = now.replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            y_true = y_true[:end_time]
            y_preds_base = [pred[:len(y_true)] for pred in y_preds_base]
            y_pred_ensemble = y_pred_ensemble[:len(y_true)]
        # Ensure y_true is a NumPy array
        if isinstance(y_true, (pd.DataFrame, pd.Series)):
            y_true = y_true.to_numpy()
        if y_true.ndim == 1:
            y_true = y_true.reshape(-1, 1)
            
        y_preds_base = [pred.to_numpy() if isinstance(pred, pd.DataFrame) else pred for pred in y_preds_base]
        y_preds_base = [pred.reshape(-1, 1) if pred.ndim == 1 else pred for pred in y_preds_base]
        
        y_pred_ensemble = y_pred_ensemble.to_numpy() if isinstance(y_pred_ensemble, pd.DataFrame) else y_pred_ensemble
        if y_pred_ensemble.ndim == 1:
            y_pred_ensemble = y_pred_ensemble.reshape(-1, 1)
        
        metrics = ['R2 Score', 'Adjusted R2', 'MSE', 'MAE', 'MAPE', 'WMAPE', 'SMAPE', 'CV(RMSE)', 'NMBE', 'RMSE', 'VIF']
        evaluation_metrics = [metric + ' 평가' for metric in metrics]
        results = []
        evaluations = []
        
        # 베이스 모델 성능 평가
        for i, y_pred in enumerate(y_preds_base):
            r2_scores = [r2_score(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            adj_r2_scores = [adjusted_r2(y_true[:, j], y_pred[:, j], y_pred.shape[1]) for j in range(y_true.shape[1])]
            mse_scores = [mean_squared_error(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            mae_scores = [mean_absolute_error(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            mape_scores = [mean_absolute_percentage_error(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            wmape_scores = [weighted_mean_absolute_percentage_error(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            smape_scores = [symmetric_mean_absolute_percentage_error(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            cv_rmse_scores = [coefficient_of_variation_rmse(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            nmbe_scores = [normalized_mean_bias_error(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            rmse_scores = [rmse(y_true[:, j], y_pred[:, j]) for j in range(y_true.shape[1])]
            vif_scores = calculate_vif(y_pred)

            vif_mean = np.mean(vif_scores)
            avg_r2, avg_adj_r2, avg_mse, avg_mae, avg_mape, avg_wmape, avg_smape, avg_cv_rmse, avg_nmbe, avg_rmse = map(np.mean, [r2_scores, adj_r2_scores, mse_scores, mae_scores, mape_scores, wmape_scores,
                                    smape_scores, cv_rmse_scores, nmbe_scores, rmse_scores])
            results.append([f'Base Model {i+1}', avg_r2, avg_adj_r2, avg_mse, avg_mae, avg_mape, avg_wmape, avg_smape, avg_cv_rmse, avg_nmbe, avg_rmse, vif_mean])
            evaluations.append(evaluate_performance(avg_r2, avg_adj_r2, avg_mse, avg_mae, avg_mape, avg_wmape, avg_smape, avg_cv_rmse, avg_nmbe, avg_rmse, vif_mean))
    
        # 앙상블 모델 성능 평가 추가
        r2_scores = [r2_score(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        adj_r2_scores = [adjusted_r2(y_true[:, j], y_pred_ensemble[:, j], y_pred_ensemble.shape[1]) for j in range(y_true.shape[1])]
        mse_scores = [mean_squared_error(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        mae_scores = [mean_absolute_error(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        mape_scores = [mean_absolute_percentage_error(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        wmape_scores = [weighted_mean_absolute_percentage_error(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        smape_scores = [symmetric_mean_absolute_percentage_error(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        cv_rmse_scores = [coefficient_of_variation_rmse(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        nmbe_scores = [nmbe(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        rmse_scores = [rmse(y_true[:, j], y_pred_ensemble[:, j]) for j in range(y_true.shape[1])]
        vif_scores = calculate_vif(y_pred_ensemble)
        vif_mean = np.mean(vif_scores)
        avg_r2, avg_adj_r2, avg_mse, avg_mae, avg_mape, avg_wmape, avg_smape, avg_cv_rmse, avg_nmbe, avg_rmse = map(np.mean, [r2_scores, adj_r2_scores, mse_scores, mae_scores, mape_scores, wmape_scores,
                                    smape_scores, cv_rmse_scores, nmbe_scores, rmse_scores])
        results.append([f'Ensemble Model', avg_r2, avg_adj_r2, avg_mse, avg_mae, avg_mape, avg_wmape, avg_smape, avg_cv_rmse, avg_nmbe, avg_rmse, vif_mean])
        evaluations.append(evaluate_performance(avg_r2, avg_adj_r2, avg_mse, avg_mae, avg_mape, avg_wmape, avg_smape, avg_cv_rmse, avg_nmbe, avg_rmse, vif_mean))
        
        # 결과 데이터프레임 생성
        df_results = pd.DataFrame(results, columns=['Model'] + metrics)
        df_evaluations = pd.DataFrame(evaluations, columns=evaluation_metrics)
        df_results = pd.concat([df_results, df_evaluations], axis=1)
        
        conclusion, recommendations = generate_final_conclusion(df_results)
        
        return df_results, conclusion, recommendations