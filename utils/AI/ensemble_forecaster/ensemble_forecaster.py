# ensemble_forecaster.py
import json
import pandas as pd
import os, joblib
import numpy as np
import tensorflow as tf
from sklearn.model_selection import KFold, RandomizedSearchCV, TimeSeriesSplit, cross_val_score
from joblib import parallel_backend
from keras_tuner import HyperModel, RandomSearch, BayesianOptimization
from sklearn.metrics import make_scorer, r2_score # 이미 optuna_fine_tune에 있을 수 있지만, 명시적으로 추가

# 🔥 각 모델별 클래스 임포트
from .config import DefaultConfig, ensembleForecaster_logger
from .models import *
from .optimize import create_sequence
from .utilities import (
    normalized_mean_bias_error, rmse, save_ml_tuning_report, 
    get_next_trial_path, adjusted_r2, mean_absolute_percentage_error, 
    weighted_mean_absolute_percentage_error, symmetric_mean_absolute_percentage_error, 
    coefficient_of_variation_rmse, get_latest_trial_path
)

"""
EnsembleForecaster
- 여러 딥러닝 모델 학습, 튜닝, 예측
- 최적 앙상블 가중치 자동 탐색
- 특성 추출, 저장/로딩 기능 제공
"""

class EnsembleForecaster:
    def __init__(self, config=None, logger=None):
        self.config = config or DefaultConfig()
        self.logger = logger or ensembleForecaster_logger
        self.models = {}                # 학습된 모델 저장
        self.tuned_models = {}          # 튜닝된 모델 저장
        self.tuned_params = {}          # 튜닝된 하이퍼파라미터 저장
        self.ensemble_weights = None    # 앙상블 가중치
        self.stacking_model = None      # 스태킹 메타 모델 저장
        self.ensemble_strategy = None   # 최종 앙상블 전략 ('stacking' or 'weighted_average')
        self.models['final_ensemble'] = None # 최종 선택된 앙상블 모델 또는 가중치 정보
        
    # -------------------------------
    # 1. 모델 학습 및 예측
    # -------------------------------

    def train(self, model_name, X_train, y_train, epochs=50, batch_size=32, **kwargs):
        """
        단일 모델 학습
        """
        model_class = self._get_model_class(model_name)
        model_instance = model_class(self.config)
        model = model_instance.build(X_train, y_train, **kwargs)

        model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size, verbose=1)
        self.models[model_name] = model

    def predict(self, model_name, X_test):
        """
        단일 모델 예측
        """
        
        if isinstance(X_test, pd.DataFrame):
            X_test = X_test.to_numpy()
            if len(X_test.shape) == 2:
                X_test = np.expand_dims(X_test, axis=0)
        model = self.models[f'best_{model_name}']
        pred = model.predict(X_test)
        return pred

    def ensemble_predict(self, model_names, X_test, weights=None):
        """
        앙상블 예측 (평균 or 가중 평균)
        """

        preds = [self.predict(name, X_test) for name in model_names]
        preds = np.array(preds)

        if weights is None:
            weights = np.ones(len(preds)) / len(preds)
        weights = np.array(weights).reshape(-1, 1, 1, 1)

        weighted_preds = preds * weights
        ensemble_pred = np.sum(weighted_preds, axis=0)
        return ensemble_pred

    # -------------------------------
    # 2. 모델 저장 및 로딩
    # -------------------------------
               
    def save_all_models(self, base_dir="models", trial_num=None):
        """
        모든 모델을 models/trial_숫자/에 저장
        """
        save_path = get_next_trial_path(base_dir, trial_num=trial_num)
        for name, model in self.models.items():
            try:
                if hasattr(model, "save"):  # Keras 모델
                    model.save(os.path.join(save_path, f"{name}.h5"))
                    self.logger.info(f"🔵 {name}: Keras 모델 저장 완료")
                else:
                    joblib.dump(model, os.path.join(save_path, f"{name}.pkl"))
                    self.logger.info(f"🟢 {name}: 머신러닝 모델 저장 완료")
            except Exception as e:
                self.logger.error(f"모델 저장 실패 ({name}): {e}")


    def load_all_models(self, base_dir="models", trial_num=None):
        """
        models/trial_숫자/ 에서 모든 모델 불러오기
        """
        load_path = get_latest_trial_path(base_dir, trial_num)

        for file in os.listdir(load_path):
            file_path = os.path.join(load_path, file)
            model_name = file.split(".")[0]
            self.logger.info(f"모델 로딩: {file_path}/{model_name}")
            try:
                if file.endswith(".h5"):
                    self.logger.info(f"🔵 {model_name}: Keras 모델 로딩")
                    model = tf.keras.models.load_model(file_path, compile=False)
                elif file.endswith(".pkl"):
                    self.logger.info(f"🟢 {model_name}: 머신러닝 모델 로딩")
                    model = joblib.load(file_path)
                else:
                    continue

                self.models[model_name] = model

            except Exception as e:
                self.logger.error(f"{model_name} 모델 로딩 실패: {e}")

    def _deduplicate_by_threshold(self, values, threshold):
        """
        값 기준으로 정렬 후, 인접 값의 차이가 threshold 이하이면 하나만 남기고 제외
        """
        if not values:
            return []
        sorted_values = sorted(values)
        deduped = [sorted_values[0]]
        for v in sorted_values[1:]:
            if abs(v - deduped[-1]) > threshold:
                deduped.append(v)
        return deduped
        
    def summarize_hyperparameter_tuning_results(self, ref_report=40):
        """
        하이퍼파라미터 튜닝 결과를 모델별로 집계하여 최빈값을 JSON 파일로 저장합니다.
        연속형 파라미터는 최대-최소의 5%를 threshold로, 값 기준 정렬 후 인접 값의 차이가 threshold 이하이면 하나만 남기고 제외합니다.
        이후 상위 5개만 남깁니다.
        """
        from collections import Counter
        import glob
        import os
        import json

        hyperparams_path = self.config.hyperparameters_save_path
        if not os.path.exists(hyperparams_path):
            self.logger.error(f"Hyperparameters directory not found: {hyperparams_path}")
            return

        model_tuning_folders = glob.glob(os.path.join(hyperparams_path, "*_tuning"))
        summary_data = {}
        total_trials = 0

        for folder in model_tuning_folders:
            model_name_full = os.path.basename(folder).replace("_tuning", "")
            ml_report_files = glob.glob(os.path.join(hyperparams_path, folder.split(os.sep)[-1] + ".json"))
            # 원래 report_files 계산부
            report_files = list(set(ml_report_files + glob.glob(os.path.join(folder, "**", "trial.json"), recursive=True)))
            total_trials += len(report_files)

            if not report_files:
                self.logger.warning(f"No tuning report files found in {folder} or its subdirectories.")
                continue

            all_params_for_model = {}
            for report_file in report_files:
                try:
                    with open(report_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        params = None
                        # ML trial.json: 경로에 'ML'이 포함되어 있으면 best_params/cleaned_params 파싱
                        if os.path.basename(report_file).lower() == 'trial.json':
                            if 'ML' in report_file or 'ml' in report_file:
                                params = data.get('best_params') or data.get('cleaned_params')
                            elif 'hyperparameters' in data and isinstance(data['hyperparameters'], dict) and 'values' in data['hyperparameters']:
                                params = data['hyperparameters']['values']
                            else:
                                self.logger.warning(f"File {report_file} is named trial.json but lacks expected Keras Tuner or ML structure. Skipping.")
                        if params is None:
                            params = data.get('best_params') or data.get('cleaned_params')
                        if params and isinstance(params, dict):
                            for param_name, param_value in params.items():
                                if param_name not in all_params_for_model:
                                    all_params_for_model[param_name] = []
                                all_params_for_model[param_name].append(str(param_value))
                        elif params is not None:
                            self.logger.warning(f"Parameters in {report_file} are not in the expected dictionary format. Skipping this entry. Params: {params}")
                except json.JSONDecodeError:
                    self.logger.error(f"Error decoding JSON from {report_file}")
                except Exception as e:
                    self.logger.error(f"Error processing file {report_file}: {e}")

            if not all_params_for_model:
                self.logger.warning(f"No valid parameters found for model {model_name_full} in {folder}")
                continue

            model_summary = {}
            for param_name, values_list in all_params_for_model.items():
                if not values_list:
                    model_summary[param_name] = None
                    continue
                is_numeric_list = True
                numeric_values = []
                try:
                    for s_val in values_list:
                        numeric_values.append(float(s_val))
                except ValueError:
                    is_numeric_list = False

                actual_value = None
                if is_numeric_list and numeric_values:
                    unique_sorted_values = sorted(list(set(numeric_values)))
                    if not unique_sorted_values:
                        pass
                    elif len(unique_sorted_values) == 1:
                        val = unique_sorted_values[0]
                        formatted_val = int(round(val)) if np.isclose(val, round(val)) else float(val)
                        deduped = [formatted_val]
                    else:
                        data_min = unique_sorted_values[0]
                        data_max = unique_sorted_values[-1]
                        data_range = data_max - data_min
                        threshold = data_range * 0.1 if data_range > 1e-9 else 0.0
                        deduped = self._deduplicate_by_threshold(unique_sorted_values, threshold)
                        deduped = [int(round(v)) if np.isclose(v, round(v)) else float(v) for v in deduped]
                    # 5개 초과시 중앙값에 가까운 순서로 3개만 남김
                    if len(deduped) > 3:
                        median = np.median(deduped)
                        deduped = sorted(deduped, key=lambda x: abs(x - median))[:3]
                    if isinstance(deduped, list) and len(deduped) == 1:
                        actual_value = deduped[0]
                    else:
                        actual_value = deduped
                if actual_value is None or not is_numeric_list:
                    count = Counter(values_list)
                    if not count:
                        model_summary[param_name] = None
                        continue
                    # 최빈값 5순위만 남김
                    most_common_values = count.most_common(3)
                    result_list = []
                    for v, _ in most_common_values:
                        # 타입 변환
                        if isinstance(v, str):
                            v_lower = v.lower()
                            if v_lower == 'true':
                                result_list.append(True)
                            elif v_lower == 'false':
                                result_list.append(False)
                            elif v_lower == 'none' or v_lower == 'null':
                                result_list.append(None)
                            else:
                                try:
                                    result_list.append(int(v))
                                except ValueError:
                                    try:
                                        result_list.append(float(v))
                                    except ValueError:
                                        result_list.append(v)
                        else:
                            result_list.append(v)
                    # 1개만 있으면 단일값, 여러 개면 리스트
                    actual_value = result_list[0] if len(result_list) == 1 else result_list
                else:
                    if isinstance(actual_value, list) and len(actual_value) == 1:
                        actual_value = actual_value[0]
                model_summary[param_name] = actual_value
            if model_summary:
                summary_data[model_name_full] = model_summary
            else:
                self.logger.warning(f"Could not generate summary for model {model_name_full}")
        # Summarization done for all models, now decide whether to write file
        if total_trials <= ref_report:
            self.logger.warning(f"Total trial files ({total_trials}) ≤ {ref_report}; skipping summary file creation.")
            return
        output_filename = os.path.join(hyperparams_path, "model_hyperparameter_summary.json")
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=4)
            self.logger.info(f"Hyperparameter summary saved to {output_filename}")
        except Exception as e:
            self.logger.error(f"Failed to save hyperparameter summary: {e}")
            
    # -------------------------------
    # 3. 하이퍼파라미터 튜닝
    # -------------------------------

    def tune(self, model_name, X_train, y_train, max_trials=10, batch_size=32, epochs=50, model_list=[]):
        tuner_type = "random"
        base_self = self
        model_class = self._get_model_class(model_name)
        model_type = getattr(model_class, 'model_type', 'DL')  # 없으면 DL 기본
        # Config에서 해당 모델의 Search Space 가져오기
        hyperparameter_space = self.config.hyperparameter_grids.get(model_name.capitalize() + "Model", {})
        
        # Define custom scoring metrics for ML tuning
        def metric_r2(y_true, y_pred):
            return r2_score(y_true, y_pred)
        def metric_adj_r2(y_true, y_pred):
            return adjusted_r2(y_true, y_pred, X_train.shape[1] if hasattr(X_train, 'shape') else 1)
        def metric_rmse(y_true, y_pred):
            return rmse(y_true, y_pred)
        def metric_abs_nmbe(y_true, y_pred):
            return abs(normalized_mean_bias_error(y_true, y_pred))
        def metric_mape(y_true, y_pred):
            return mean_absolute_percentage_error(y_true, y_pred)
        def metric_wmape(y_true, y_pred):
            return weighted_mean_absolute_percentage_error(y_true, y_pred)
        def metric_smape(y_true, y_pred):
            return symmetric_mean_absolute_percentage_error(y_true, y_pred)
        def metric_cv_rmse(y_true, y_pred):
            return coefficient_of_variation_rmse(y_true, y_pred)

        scoring = {
            "r2": make_scorer(metric_r2),
            "adj_r2": make_scorer(metric_adj_r2),
            "rmse": make_scorer(metric_rmse, greater_is_better=False),
            "abs_nmbe": make_scorer(metric_abs_nmbe, greater_is_better=False),
            "mape": make_scorer(metric_mape, greater_is_better=False),
            "wmape": make_scorer(metric_wmape, greater_is_better=False),
            "smape": make_scorer(metric_smape, greater_is_better=False),
            "cv_rmse": make_scorer(metric_cv_rmse, greater_is_better=False),
        }
        
        if model_type == 'ML':  # 머신러닝
            # 머신러닝용 build 함수
            estimator = model_class(self.config).build(X_train, y_train)  # 모델 인스턴스 생성
            
            # param_grid 준비 (ML은 그대로 씀)
            param_grid = {k: v for k, v in hyperparameter_space.items()}
            for param in ['n_jobs', 'thread_count']:
                key = f"estimator__{param}"
                if key in param_grid:
                    param_grid[key] = [1]
            tuner = RandomizedSearchCV(
                estimator=estimator,
                param_distributions={f"estimator__{k}": v for k, v in param_grid.items()},
                n_iter=max_trials,
                cv=TimeSeriesSplit(n_splits=batch_size),
                scoring=scoring,
                n_jobs=self.config.cpu_count,
                pre_dispatch="2*n_jobs",
                verbose=2,
                random_state=42,
                error_score=np.nan,  # 실패는 NaN
                return_train_score=True,  # 훈련 점수도 반환
                refit="r2",         # 어떤 metric으로 best 선택할지 명시
            )
            # sample_weight 생성
            sample_weight = None
            
            if hasattr(self.config, "sample_weight_func") and callable(self.config.sample_weight_func):
                sample_weight = self.config.sample_weight_func(X_train, y_train)
                self.logger.info(f"[BaseModel] sample_weight 적용됨")
                
            with parallel_backend("threading", n_jobs=self.config.cpu_count):
                if sample_weight is not None:
                    tuner.fit(X_train, y_train, sample_weight=sample_weight)
                else:
                    tuner.fit(X_train, y_train)
            best_params = tuner.best_params_
            cleaned_params = {k.split('__')[1]: v for k, v in best_params.items() if k.startswith("estimator__")}
            # Optuna 미세조정 추가
            metric_score = None
            try:
                _, cleaned_params, metric_score = self.optuna_fine_tune(
                    model_name, X_train, y_train, cleaned_params, max_trials=max_trials*5, batch_size=batch_size,
                )
            except Exception as e:
                self.logger.error(f"Optuna 미세조정 실패: {e}") 
                
            best_model = model_class(self.config).build_best_model(X_train, y_train, cleaned_params, sample_weight=sample_weight)
            if metric_score is not None:
                self.logger.info(f"Best metric score for {model_name}: {metric_score}")
            save_ml_tuning_report(model_name=model_name, cleaned_params=cleaned_params, metric_score=metric_score, report_dir=f'{self.config.hyperparameters_save_path}{model_name.lower()}_tuning')
            self.logger.info(f"Best parameters saved to {model_name.lower()}_tuning")
            self.models[f'best_{model_name}'] = best_model
            self.logger.info(f"Best model saved to {model_name.lower()}_tuning")
            self.tuned_params[model_name] = cleaned_params
        elif model_type == 'ensemble_ML':
            # OOF(Out-Of-Fold) stacking 구조로 base 모델 예측값 생성
            tscv = TimeSeriesSplit(n_splits=batch_size)
            oof_preds = {base_model_name: np.zeros_like(y_train, dtype=float) for base_model_name in model_list if model_name != base_model_name}
            for fold, (train_idx, valid_idx) in enumerate(tscv.split(X_train, y_train)):
                self.logger.info(f"[OOF Stacking][Fold {fold}] {X_train.shape} {y_train.shape} 시작...")
                X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[valid_idx]
                y_tr, y_val = y_train.iloc[train_idx], y_train.iloc[valid_idx]
                for base_model_name in model_list:
                    if model_name != base_model_name:
                        # Config에서 해당 모델의 Search Space 가져오기
                        hyperparameter_space = self.config.hyperparameter_grids.get(base_model_name.capitalize() + "Model", {})
                        self.logger.info(f"[OOF Stacking][Fold {fold}][Model {base_model_name}] Train Index({train_idx[0]}~{train_idx[-1]}), Test Index({valid_idx[0]} ~ {valid_idx[-1]}) 시작...")
                        model_class = self._get_model_class(base_model_name)
                        estimator = model_class(self.config).build(X_tr, y_tr)
                        param_grid = {f"estimator__{k}": v for k, v in hyperparameter_space.items()}
                        for param in ['n_jobs', 'thread_count']:
                            key = f"estimator__{param}"
                            if key in param_grid:
                                param_grid[key] = [1]
                        # 튜닝된 파라미터가 있다면 param_grid에 추가하는데 param_grid의 값이 리스트인경우 append만 처리
                        for param in self.tuned_params[base_model_name]:
                            if param in param_grid:
                                if isinstance(param_grid[param], list):
                                    param_grid[param].append(self.tuned_params[base_model_name][param])

                        # sample_weight 생성
                        sample_weight = None
                        if hasattr(self.config, "sample_weight_func") and callable(self.config.sample_weight_func):
                            sample_weight = self.config.sample_weight_func(X_tr, y_tr)
                            self.logger.info(f"[OOF Stacking][Fold {fold}][Model {base_model_name}] sample_weight 적용 완료")

                        tuner = RandomizedSearchCV(
                            estimator=estimator,
                            param_distributions=param_grid,
                            n_iter=max_trials,
                            cv=2,
                            scoring=scoring,
                            n_jobs=-1,
                            pre_dispatch="2*n_jobs",
                            verbose=2,
                            random_state=42,
                            error_score=np.nan,  # 실패는 NaN
                            return_train_score=True,
                            refit="r2",         # 어떤 metric으로 best 선택할지 명시
                        )
                        with parallel_backend("threading", n_jobs=self.config.cpu_count):
                            tuner.fit(X_tr, y_tr, sample_weight=sample_weight)
                        best_estimator = tuner.best_estimator_
                        preds = best_estimator.predict(X_val)
                        # OOF 예측값 저장
                        if preds.ndim == 1:
                            oof_preds[base_model_name][valid_idx] = preds
                        else:
                            oof_preds[base_model_name][valid_idx, :] = preds
            hyperparameter_space = self.config.hyperparameter_grids.get(model_name.capitalize() + "Model", {})
            model_class = self._get_model_class(model_name)
            # OOF 예측값을 meta feature로 사용
            meta_X = np.column_stack([oof_preds[base_model_name] for base_model_name in oof_preds])
            meta_y = y_train
            # 머신러닝용 build 함수
            estimator = model_class(self.config).build(meta_X, meta_y)  # 모델 인스턴스 생성
            # param_grid 준비 (ML은 그대로 씀)
            param_grid = {k: v for k, v in hyperparameter_space.items()}
            # meta_X, meta_y로 meta model 튜닝
            tuner = RandomizedSearchCV(
                estimator=estimator,
                param_distributions={f"estimator__{k}": v for k, v in param_grid.items()},
                n_iter=max_trials,
                cv=TimeSeriesSplit(n_splits=batch_size),
                scoring=scoring,
                n_jobs=self.config.cpu_count,
                pre_dispatch="2*n_jobs",
                verbose=2,
                random_state=42,
                error_score=np.nan,
                return_train_score=True,
                refit="r2",         # 어떤 metric으로 best 선택할지 명시
            )
            with parallel_backend("threading", n_jobs=self.config.cpu_count):
                tuner.fit(meta_X, meta_y)
            # 최적 파라미터 추출
            best_params = tuner.best_params_
            
            # 'estimator__' 접두어 제거
            cleaned_params = {k.split('__')[1]: v for k, v in best_params.items() if k.startswith("estimator__")}
            
            # Optuna 미세조정 추가
            try:
                _, cleaned_params, metric_score = self.optuna_fine_tune(
                    model_name, meta_X, meta_y, cleaned_params, max_trials=max_trials*5, batch_size=batch_size
                )
            except Exception as e:
                self.logger.error(f"Optuna 미세조정 실패: {e}") 
            if metric_score is not None:
                self.logger.info(f"Best metric score for {model_name}: {metric_score}")
            # 최적 모델 생성
            best_model = model_class(self.config).build_best_model(meta_X, meta_y, cleaned_params)
            save_ml_tuning_report(model_name=model_name, cleaned_params=cleaned_params, report_dir=f'{self.config.hyperparameters_save_path}{model_name.lower()}_tuning')
            self.logger.info(f"Best parameters saved to {model_name.lower()}_tuning")
            self.logger.info(f"Best model saved to {model_name.lower()}_tuning")
            self.models[f'best_{model_name}'] = best_model
        else:
            self.X_seq, self.y_seq = create_sequence(X_train, y_train, input_window=self.config.input_seq_len, output_window=self.config.output_seq_len, step_size=self.config.step_size)
            build_func = self.get_build_func(model_name, base_self, self.X_seq, self.y_seq)
                    
            """ 모델 하이퍼파라미터 튜닝 (Keras Tuner) """
            class TunerHyperModel(HyperModel):
                def build(self, hp):
                    if hyperparameter_space:
                        for param_name, values in hyperparameter_space.items():
                            if isinstance(values[0], float):
                                hp.Float(param_name, min(values), max(values))
                            elif isinstance(values[0], int):
                                hp.Int(param_name, min(values), max(values))
                            elif isinstance(values[0], str):
                                hp.Choice(param_name, values)
                            else:
                                raise ValueError(f"Unsupported hyperparameter type for {param_name}: {values}")
                    return build_func(hp)
                
            # 튜너 선택
            if tuner_type == "random":
                tuner_cls = RandomSearch
            elif tuner_type == "bayesian":
                tuner_cls = BayesianOptimization
            else:
                raise ValueError(f"Unknown tuner_type: {self.tuner_type}")
            tuner = tuner_cls(
                TunerHyperModel(),
                objective='loss',
                max_trials=max_trials,
                executions_per_trial=1,
                directory=f'{model_name.lower()}_tuning',
                project_name=f'{model_name.lower()}_project',
                overwrite=True
            )
            tuner.search(self.X_seq, self.y_seq, epochs=epochs, batch_size=batch_size, verbose=1)

            self.logger.info(f"Best parameters saved to {model_name.lower()}_tuning")
            self.logger.info(f"Best model saved to {model_name.lower()}_tuning")
            # 최적 모델 저장
            best_model = tuner.get_best_models(num_models=1)[0]
            best_model.compile(optimizer='adam', loss='mse', metrics=['mae'])
            self.models[f'best_{model_name}'] = best_model


    def auto_tune(self, model_list, X_train, y_train, max_trials=10, batch_size=32, epochs=50):
        """ 여러 모델 자동 튜닝 """
        for model_name in model_list:
            self.logger.info(f"[튜닝] {model_name} 시작...")
            self.tune(model_name, X_train, y_train, max_trials=max_trials, batch_size=batch_size, epochs=epochs, model_list=model_list)
            self.tuned_models[model_name] = self.models[f'best_{model_name}']

        # ✅ 튜닝 완료 후 저장된 모델 리스트 출력
        self.logger.info("\n✅ 튜닝 완료: 저장된 모델 리스트")
        for model_name in self.tuned_models.keys():
            self.logger.info(f" - {model_name}")
  
    # -------------------------------
    # 3-2. Optuna 미세조정 튜닝
    # -------------------------------
    def optuna_fine_tune(self, model_name, X_train, y_train, best_params, max_trials=20, batch_size=32):
        import optuna # 메서드 내에서 import 하는 것이 충돌 방지에 유리할 수 있음
        from sklearn.model_selection import TimeSeriesSplit, cross_val_score # 추가
        from sklearn.metrics import r2_score # 명시적 import

        model_class = self._get_model_class(model_name)
        num_features = X_train.shape[1] if hasattr(X_train, 'shape') else 1 # For adjusted_r2
        model_type = getattr(model_class, 'model_type', 'DL')  # ensemble_ML

        try:
            base_model_for_r2_calc = model_class(self.config).build_best_model(X_train, y_train, best_params)
            num_cv_splits_for_r2 = min(batch_size, len(X_train) - 1 if len(X_train) > 1 else 2)
            if num_cv_splits_for_r2 < 2 : num_cv_splits_for_r2 = 2
            cv_splitter_for_r2 = TimeSeriesSplit(n_splits=num_cv_splits_for_r2)
            base_r2 = np.mean(cross_val_score(
                base_model_for_r2_calc, X_train, y_train,
                cv=cv_splitter_for_r2,
                scoring='r2',
                error_score='raise'
            ))
        except Exception as e:
            self.logger.error(f"[Optuna MOO] base_r2 계산 실패: {e}")
            base_r2 = 0.0

        if base_r2 <= 0:
            ratio = 0.5
        elif base_r2 >= 0.8:
            ratio = 0.2
        else:
            config_ratio = self.config.optuna_neighborhood_ratio.get(model_name, 1.0)
            ratio = min(0.5, max(0.1, abs(base_r2 - 0.8) * config_ratio))
        self.logger.info(f"[Optuna MOO] {model_name} base_r2: {base_r2:.4f}, neighborhood ratio for param search: {ratio:.3f}")

        tune_params_list = self.config.optuna_neighborhood_params.get(model_name, list(best_params.keys()))
        if not tune_params_list:
            self.logger.warning(f"[Optuna MOO] {model_name} 미세조정 대상 파라미터가 없습니다. 미세조정 생략.")
            final_model_instance = model_class(self.config).build_best_model(X_train, y_train, best_params)
            return final_model_instance, best_params, None

        def objective(trial):
            current_params = best_params.copy()
            for param_name in tune_params_list:
                if param_name not in best_params:
                    continue
                original_value = best_params[param_name]

                if isinstance(original_value, float):
                    val_delta = abs(original_value) * ratio if original_value != 0 else ratio 
                    low_bound = original_value - val_delta
                    high_bound = original_value + val_delta
                    if param_name in ["bagging_fraction", "feature_fraction", "colsample_bytree", "subsample", "dropout_rate", "learning_rate"]:
                        low_bound = max(1e-5, low_bound) 
                        high_bound = min(1.0 - 1e-5, high_bound) 
                    if low_bound >= high_bound: 
                        low_bound = original_value * 0.9 if original_value > 1e-4 else original_value - 1e-4 
                        high_bound = original_value * 1.1 if original_value > 1e-4 else original_value + 1e-4
                        if low_bound == high_bound : high_bound = low_bound + 1e-4 
                    if low_bound < 0:
                        low_bound = 0
                    current_params[param_name] = trial.suggest_float(param_name, low_bound, high_bound)
                elif isinstance(original_value, int):
                    val_delta = max(1, int(abs(original_value) * ratio))
                    low_bound = original_value - val_delta
                    high_bound = original_value + val_delta
                    if param_name in ["depth", "num_leaves", "min_child_samples", "n_estimators", "leaf_estimation_iterations", "num_layers", "lstm_units", "hidden_units", "d_model", "patch_len", "stride", "n_heads", "factor", "conv_filters", "attention_heads", "transformer_units", "max_depth", "min_samples_split", "min_samples_leaf"]:
                        low_bound = max(1, low_bound) 
                    if low_bound >= high_bound:
                        low_bound = max(1, original_value - val_delta if original_value - val_delta > 0 else 1)
                        high_bound = original_value + val_delta + 1 
                    if low_bound < 0:
                        low_bound = 0
                    current_params[param_name] = trial.suggest_int(param_name, low_bound, high_bound)
                elif isinstance(original_value, str):
                    current_params[param_name] = trial.suggest_categorical(param_name, [original_value])
                else: 
                    current_params[param_name] = trial.suggest_categorical(param_name, [original_value])

                        
            # sample_weight 적용
            sample_weight = None
            
            if hasattr(self.config, "sample_weight_func") and callable(self.config.sample_weight_func):
                try:
                    # 함수가 scale 인자를 받는 경우
                    sample_weight = self.config.sample_weight_func(X_train, y_train)
                except TypeError:
                    # scale 인자를 받지 않는 단순한 경우
                    sample_weight = self.config.sample_weight_func(X_train, y_train)
            if model_type == 'ensemble_ML':
                temp_model = model_class(self.config).build_best_model(X_train, y_train, current_params)
            else:
                temp_model = model_class(self.config).build_best_model(X_train, y_train, current_params, sample_weight=sample_weight)
            
            try:
                num_cv_splits = min(batch_size, len(X_train) // 2 if len(X_train) // 2 >=2 else 2) 
                if num_cv_splits < 2 : num_cv_splits = 2 
                cv_eval = TimeSeriesSplit(n_splits=num_cv_splits)
                
                fold_y_preds, fold_y_trues = [], []
                
                for train_idx, test_idx in cv_eval.split(X_train):
                    X_tr_fold, X_te_fold = (X_train.iloc[train_idx], X_train.iloc[test_idx]) if isinstance(X_train, (pd.DataFrame, pd.Series)) else (X_train[train_idx], X_train[test_idx])
                    y_tr_fold, y_te_fold = (y_train.iloc[train_idx], y_train.iloc[test_idx]) if isinstance(y_train, (pd.DataFrame, pd.Series)) else (y_train[train_idx], y_train[test_idx])
                        
                    # sample_weight 적용
                    sample_weight = None
                    
                    if hasattr(self.config, "sample_weight_func") and callable(self.config.sample_weight_func):
                        try:
                            # 함수가 scale 인자를 받는 경우
                            sample_weight = self.config.sample_weight_func(X_tr_fold, y_tr_fold)
                        except TypeError:
                            # scale 인자를 받지 않는 단순한 경우
                            sample_weight = self.config.sample_weight_func(X_tr_fold, y_tr_fold)
                            
                    if sample_weight is not None:
                        temp_model.fit(X_tr_fold, y_tr_fold, sample_weight=sample_weight)
                    else:
                        temp_model.fit(X_tr_fold, y_tr_fold)
                        
                    preds_fold = temp_model.predict(X_te_fold)
                    fold_y_preds.append(preds_fold.flatten()) 
                    fold_y_trues.append(y_te_fold.to_numpy().flatten() if hasattr(y_te_fold, 'to_numpy') else np.array(y_te_fold).flatten())

                y_preds_aggregated = np.concatenate(fold_y_preds)
                y_trues_aggregated = np.concatenate(fold_y_trues)

                # 기존 지표
                metric_r2 = r2_score(y_trues_aggregated, y_preds_aggregated)
                metric_rmse = rmse(y_trues_aggregated, y_preds_aggregated) 
                metric_nmbe_signed = normalized_mean_bias_error(y_trues_aggregated, y_preds_aggregated)
                metric_abs_nmbe = abs(metric_nmbe_signed)

                # 추가된 지표 계산
                metric_adj_r2 = adjusted_r2(y_trues_aggregated, y_preds_aggregated, num_features)
                metric_mape = mean_absolute_percentage_error(y_trues_aggregated, y_preds_aggregated)
                metric_wmape = weighted_mean_absolute_percentage_error(y_trues_aggregated, y_preds_aggregated)
                metric_smape = symmetric_mean_absolute_percentage_error(y_trues_aggregated, y_preds_aggregated)
                metric_cv_rmse = coefficient_of_variation_rmse(y_trues_aggregated, y_preds_aggregated)
                
                all_metrics = [
                    metric_r2, metric_adj_r2, metric_rmse, metric_abs_nmbe, 
                    metric_mape, metric_wmape, metric_smape, metric_cv_rmse
                ]

                if any(np.isnan(m) for m in all_metrics):
                    self.logger.warning(f"[Optuna MOO] NaN in metrics for trial {trial.number}. Metrics: {all_metrics}")
                    return -np.inf, -np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf 

                return tuple(all_metrics)

            except Exception as e:
                self.logger.error(f"[Optuna MOO] Error in objective for trial {trial.number}: {e}", exc_info=True)
                return -np.inf, -np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf 

        # R2, AdjR2 (Maximize), RMSE, AbsNMBE, MAPE, WMAPE, SMAPE, CV_RMSE (Minimize)
        study = optuna.create_study(directions=[
            "maximize", "maximize", "minimize", "minimize", 
            "minimize", "minimize", "minimize", "minimize"
        ])
        study.optimize(objective, n_trials=max_trials, n_jobs=self.config.cpu_count) # n_trials 조정 가능

        self.logger.info(f"[Optuna MOO] Optimization finished. Number of Pareto optimal trials: {len(study.best_trials)}")
        
        if not study.best_trials:
            self.logger.warning("[Optuna MOO] No best trials found. Returning original best_params.")
            final_model_instance = model_class(self.config).build_best_model(X_train, y_train, best_params)
            return final_model_instance, best_params, None

        chosen_trial = None
        highest_r2_val = -np.inf # 첫 번째 값 (R2) 기준
        for t in study.best_trials:
            if t.values and t.values[0] is not None and not np.isinf(t.values[0]) and t.values[0] > highest_r2_val:
                highest_r2_val = t.values[0]
                chosen_trial = t
        
        if chosen_trial is None: 
            self.logger.warning("[Optuna MOO] Could not select a valid trial from Pareto front. Returning original best_params.")
            final_model_instance = model_class(self.config).build_best_model(X_train, y_train, best_params)
            return final_model_instance, best_params, None

        selected_params_from_optuna = chosen_trial.params
        final_updated_params = best_params.copy()
        final_updated_params.update(selected_params_from_optuna)

        final_model_instance = model_class(self.config).build_best_model(X_train, y_train, final_updated_params)
        
        metric_names = ["R2", "AdjR2", "RMSE", "AbsNMBE", "MAPE", "WMAPE", "SMAPE", "CV_RMSE"]
        trial_values_str = ", ".join([f"{name}: {val:.4f}" for name, val in zip(metric_names, chosen_trial.values)])
        self.logger.info(f"[Optuna MOO] {model_name} 미세조정 완료. Selected Trial Values ({trial_values_str}). Final params: {final_updated_params}")
        
        return final_model_instance, final_updated_params, chosen_trial.values

    # -------------------------------
    # 4. AutoEnsemble
    # -------------------------------

    def _DL_auto_ensemble(self, X_val, y_val):
        """
        최적 앙상블 가중치 자동 탐색
        """
        best_score = float('inf')
        best_weights = None
        model_names = list(self.tuned_models.keys())
        
        # ✅ usable_length 만큼만 사용 (72 * N)
        output_window = 72  # 3일치 (24시간 × 3)
        usable_length = (y_val.shape[0] // output_window) * output_window  # 144
        
        # ✅ y_val이 pandas DataFrame이면 numpy array로 변환
        if isinstance(y_val, pd.DataFrame):
            y_val = y_val.to_numpy()
        
        y_val = y_val[:usable_length]  # 남는 부분 자르기
        
        y_val = y_val.reshape(-1, output_window, y_val.shape[1])  # (batch, 72, feature_dim)

        for w in np.linspace(0, 1, 11):
            weights = [w, 1-w] if len(model_names) == 2 else np.ones(len(model_names)) / len(model_names)
            preds = self.ensemble_predict(model_names, X_val, weights=weights)
            

            loss = tf.reduce_mean(tf.keras.losses.mse(y_val, preds)).numpy()

            if loss < best_score:
                best_score = loss
                best_weights = weights

        self.ensemble_weights = best_weights
        self.logger.info(f"[AutoEnsemble] Best Weights: {self.ensemble_weights}, Loss: {best_score:.4f}")

    def _ML_auto_ensemble(self, model_list, X_train, y_train, X_val, y_val, max_trials=10, batch_size=32, epochs=0):
        """
        머신러닝 스태킹 앙상블 (메타모델을 GBM으로).
        성능 비교 후 가중치 앙상블로 전환 가능.
        """
        
        base_models_for_stacking = [] 
        meta_model_name_str = None    
        
        for name in model_list:
            # model_list에는 앙상블에 사용될 기본 모델들의 이름이 들어있다고 가정
            if self._get_model_class(name).model_type == 'ensemble_ML': # 메타 모델로 사용될 모델
                meta_model_name_str = name 
            elif name in self.tuned_models.keys(): # 튜닝된 기본 모델만 사용
                base_models_for_stacking.append((name, self.tuned_models[name]))
            else:
                self.logger.warning(f"[_ML_auto_ensemble] Tuned model for '{name}' not found in self.tuned_models. Skipping for base models.")
        print(f"[_ML_auto_ensemble] Base models for stacking: {base_models_for_stacking}")
        
        if meta_model_name_str is None:
            self.logger.error("[_ML_auto_ensemble] Meta model not found in model_list. Cannot proceed with stacking.")
            # 스태킹 불가 시, 바로 가중 평균으로 시도하도록 유도할 수 있음 (선택적)
            # 여기서는 일단 에러 로깅 후 종료 또는 예외 발생을 가정.
            # 또는, 이 경우에도 _DL_auto_ensemble을 호출하도록 할 수 있음.
            stacking_model_r2 = -np.inf
        else:
            # ✅ Base 모델들의 예측값 쌓기 -> meta_X 생성
            meta_X_parts = []
            valid_base_models_for_meta_x = [] # 실제 meta_X 생성에 사용된 모델들
            for name, model_instance in base_models_for_stacking:
                try:
                    preds = model_instance.predict(X_train) 
                    meta_X_parts.append(preds)
                    valid_base_models_for_meta_x.append((name, model_instance)) # 성공적으로 예측한 모델만 추가
                except Exception as e:
                    self.logger.error(f"[_ML_auto_ensemble] Error predicting with base model '{name}' for meta_X: {e}")
            
            if not meta_X_parts:
                self.logger.error("[_ML_auto_ensemble] No base model predictions generated for meta_X. Cannot proceed with stacking.")
                stacking_model_r2 = -np.inf
            else:
                meta_X = np.concatenate(meta_X_parts, axis=1)
                base_models_for_stacking = valid_base_models_for_meta_x # 예측에 성공한 모델들로 업데이트

                # self.tune을 호출하여 meta_model_name_str을 meta_X와 y_val로 튜닝
                self.logger.info(f"[_ML_auto_ensemble] Tuning meta model '{meta_model_name_str}'...")
                self.tune(meta_model_name_str.lower(), meta_X, y_train, max_trials=max_trials, batch_size=batch_size, epochs=epochs)
                
                tuned_meta_model = self.models.get(f'best_{meta_model_name_str.lower()}')

                if tuned_meta_model is None:
                    self.logger.error(f"[_ML_auto_ensemble] Meta model '{meta_model_name_str}' not found after tuning.")
                    stacking_model_r2 = -np.inf
                else:
                    self.stacking_model = tuned_meta_model
                    # 스태킹 모델 성능 평가 (X_val, y_val 사용, meta_X는 X_val에 대한 예측값임)
                    y_pred_stacking_val = self.stacking_model.predict(meta_X)
                    
                    y_val_np = y_val.to_numpy().ravel() if hasattr(y_val, 'to_numpy') else np.array(y_val).ravel()
                    y_pred_stacking_val_flat = y_pred_stacking_val.ravel()
                    
                    min_len_stack = min(len(y_val_np), len(y_pred_stacking_val_flat))
                    y_val_np_s = y_val_np[:min_len_stack]
                    y_pred_stacking_val_flat_s = y_pred_stacking_val_flat[:min_len_stack]

                    if len(y_val_np_s) > 0 and len(y_pred_stacking_val_flat_s) > 0:
                        stacking_model_r2 = r2_score(y_val_np_s, y_pred_stacking_val_flat_s)
                    else:
                        stacking_model_r2 = -np.inf # 평가 불가능
                    self.logger.info(f"[_ML_auto_ensemble] Stacking model R2 on validation set: {stacking_model_r2:.4f}")

        # 기본 모델들 성능 평가 (X_val, y_val 사용)
        base_model_r2_scores = []
        # y_val_np는 위에서 이미 정의됨 (스태킹 모델 평가 시 사용한 y_val의 numpy 변환 및 flatten 버전)
        if base_models_for_stacking: # 예측에 성공한 기본 모델이 있을 경우에만
            for name, model_instance in base_models_for_stacking:
                try:
                    y_pred_base_val = model_instance.predict(X_val)
                    y_pred_base_val_flat = y_pred_base_val.ravel()
                    
                    min_len_base = min(len(y_val_np), len(y_pred_base_val_flat))
                    y_val_np_b = y_val_np[:min_len_base]
                    y_pred_base_val_flat_b = y_pred_base_val_flat[:min_len_base]

                    if len(y_val_np_b) > 0 and len(y_pred_base_val_flat_b) > 0:
                        base_r2 = r2_score(y_val_np_b, y_pred_base_val_flat_b)
                        base_model_r2_scores.append(base_r2)
                        self.logger.info(f"[_ML_auto_ensemble] Base model '{name}' R2 on validation set: {base_r2:.4f}")
                    else:
                        self.logger.warning(f"[_ML_auto_ensemble] Could not evaluate base model '{name}' due to empty arrays after length matching.")
                except Exception as e:
                    self.logger.error(f"[_ML_auto_ensemble] Error evaluating base model '{name}': {e}")
        
        avg_base_model_r2 = np.mean(base_model_r2_scores) if base_model_r2_scores else -np.inf
        self.logger.info(f"[_ML_auto_ensemble] Average R2 of base models on validation set: {avg_base_model_r2:.4f}")

        # 성능 비교 및 최종 앙상블 전략 결정
        # stacking_model_r2가 -np.inf가 아니고, avg_base_model_r2보다 크거나 같은 경우 스태킹 선택
        if self.stacking_model is not None and stacking_model_r2 > -np.inf and stacking_model_r2 >= avg_base_model_r2:
            self.logger.info(f"[_ML_auto_ensemble] Stacking model selected. R2 ({stacking_model_r2:.4f}) >= Avg Base R2 ({avg_base_model_r2:.4f}).")
            self.models['best_gbm'] = self.stacking_model
            self.ensemble_strategy = 'stacking'
        else:
            if self.stacking_model is None or stacking_model_r2 <= -np.inf:
                self.logger.warning(f"[_ML_auto_ensemble] Stacking model is not available or failed evaluation. Switching to weighted average ensemble.")
            else: # 스태킹 모델은 있으나 성능이 더 낮은 경우
                self.logger.info(f"[_ML_auto_ensemble] Stacking model R2 ({stacking_model_r2:.4f}) < Avg Base R2 ({avg_base_model_r2:.4f}). Switching to weighted average ensemble.")
            
            # _DL_auto_ensemble 호출하여 가중 평균 앙상블 수행
            # 이 함수는 self.tuned_models를 사용하고 self.ensemble_weights를 설정한다고 가정.
            # 사용할 모델 리스트를 명시적으로 전달하는 것이 더 좋지만, 현재 _DL_auto_ensemble 시그니처를 따름.
            self.logger.info(f"[_ML_auto_ensemble] Performing weighted average ensemble using _DL_auto_ensemble.")
            try:
                self._DL_auto_ensemble(X_val, y_val) 
                self.ensemble_strategy = 'weighted_average'
                self.models['best_gbm'] = None # 가중 평균은 특정 모델 인스턴스가 아님 (가중치 사용)
                self.logger.info(f"[_ML_auto_ensemble] Weighted average ensemble selected. Weights: {self.ensemble_weights}")
            except Exception as e:
                self.logger.error(f"[_ML_auto_ensemble] Error during _DL_auto_ensemble execution: {e}. Defaulting to no specific ensemble model.")
                self.ensemble_strategy = 'none' # 또는 다른 실패 상태
                self.models['best_gbm'] = None
                self.ensemble_weights = None

        self.logger.info(f"[_ML_auto_ensemble] Final ensemble strategy: {self.ensemble_strategy}")
    # -------------------------------
    # 6. Feature Extraction (선택적)
    # -------------------------------

    def extract_features(self, model_name, X_input):
        """
        딥러닝 모델 중간 특성 추출
        """
        model, model_instance = self.models[model_name]
        feature_extractor = tf.keras.Model(
            inputs=model.input,
            outputs=model.layers[-3].output
        )
        return feature_extractor.predict(X_input)

    # -------------------------------
    # 7. 내부 함수
    # -------------------------------

    def _get_model_class(self, model_name):
        """
        모델 이름 문자열로부터 클래스 얻기
        """
        model_classes = {
            "lstm": LSTMModel,
            "bilstm": BiLSTMModel,
            "gru": GRUModel,
            "cnn": CNNModel,
            "informer": InformerModel,
            "patchtst": PatchTSTModel,
            "tft": TFTModel,
            "cnntft": CNNTFTModel,
            "cnnlstm": CNNLSTMModel,
            "gbm": GBMModel,
            "xgboost": XGBModel, 
            "lgbm": LGBMModel,
            "catboost": CatBoostModel,
        }
        return model_classes[model_name.lower()]
            
    def get_build_func(self, model_name, base_self, X_train, y_train):
        """ 
        모델 이름에 맞게 build_func 리턴하는 함수 
        (튜너가 모델을 빌드할 수 있도록 연결)
        """
        model_class = self._get_model_class(model_name)

        def build_func(hp):
            return model_class(base_self.config).build_with_hp(X_train, y_train, hp)

        return build_func
