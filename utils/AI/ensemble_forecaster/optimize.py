import os
import re
import numpy as np
import pandas as pd
import pickle
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.feature_selection import RFE
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score, KFold, TimeSeriesSplit
from utils.AI.ensemble_forecaster.config import ensembleForecaster_logger
from utils.AI.ensemble_forecaster.utilities import get_sunrise_sunset
from sklearn.feature_selection import VarianceThreshold
from statsmodels.stats.outliers_influence import variance_inflation_factor

def shuffle_weekly_blocks_keep_index(X: pd.DataFrame, y: pd.DataFrame, week_len: int = 168):
    """
    주 단위로 데이터를 셔플하되, 인덱스(DATETIME)는 유지한다.
    """
    assert len(X) == len(y)
    total_len = len(X)
    num_weeks = total_len // week_len

    # 잘리는 영역만 사용
    X = X.iloc[:num_weeks * week_len]
    y = y.iloc[:num_weeks * week_len]

    # 인덱스 유지용
    fixed_index = X.index.copy()

    # 주 단위로 나누기
    X_weeks = [X.iloc[i * week_len : (i + 1) * week_len].reset_index(drop=True) for i in range(num_weeks)]
    y_weeks = [y.iloc[i * week_len : (i + 1) * week_len].reset_index(drop=True) for i in range(num_weeks)]

    # 셔플 순서
    indices = np.arange(num_weeks)
    np.random.shuffle(indices)

    # 셔플 후 concat
    X_shuffled = pd.concat([X_weeks[i] for i in indices], ignore_index=True)
    y_shuffled = pd.concat([y_weeks[i] for i in indices], ignore_index=True)

    # 인덱스는 원래 시간 흐름대로 고정
    X_shuffled.index = fixed_index
    y_shuffled.index = fixed_index

    return X_shuffled, y_shuffled


def create_sequence(X, y, input_window=288, output_window=1, step_size=1):
    Xs, ys = [], []
    for i in range(0, len(X) - input_window - output_window + 1, step_size):
        v = X[i:(i + input_window)]
        label = y[(i + input_window):(i + input_window + output_window)]
        Xs.append(v)
        ys.append(label)
    return np.array(Xs), np.array(ys)

def filter_vif(X, thresh=5.0, max_iter=10):
    """
    반복적으로 VIF 계산하여 임계값 초과 변수 제거
    """
    cols = list(X.columns)
    for _ in range(max_iter):
        # X를 float으로 변환하여 statsmodels 호환
        X_vals = X[cols].astype(float).values
        # RuntimeWarning 무시 및 infinite 처리
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            raw_vif = [variance_inflation_factor(X_vals, i) for i in range(X_vals.shape[1])]
        # NaN 또는 inf는 큰 값으로 대체
        vif_vals = [float('inf') if (np.isnan(v) or np.isinf(v)) else v for v in raw_vif]
        max_vif = max(vif_vals)
        if max_vif <= thresh:
            break
        drop_idx = vif_vals.index(max_vif)
        cols.pop(drop_idx)
    return cols

def feature_filter_auto(
    X_train: pd.DataFrame,
    y_train: pd.Series = None,
    X_test: pd.DataFrame = None,
    variance_thresh: float = None,
    covariance_thresh: float = None,
    correlation_thresh: float = None,
    keep_ratio: float = 0.8,
    auto_tune: bool = True,
    use_cov_corr: bool = False,
    use_vif: bool = True,
    vif_thresh: float = 5.0,
    vif_max_iter: int = 10,
    return_report: bool = False,
):
    """
    자동으로 피처를 필터링하는 함수.
    - 분산 기준, 공분산/상관계수 기준, VIF 기준 등을 적용하여 피처를 선택합니다.
    
    Parameters:
    - X_train: pd.DataFrame
    - y_train: pd.Series or None (공분산/상관계수 기준 적용 시 필요)
    - X_test: pd.DataFrame or None
    - variance_thresh: float or None
    - covariance_thresh: float or None
    - correlation_thresh: float or None
    - keep_ratio: float (auto_tune=True일 때만 사용)
    - auto_tune: bool
    - use_cov_corr: bool (True면 y_train과의 공분산/상관계수 필터도 적용)
    - use_vif: bool (True면 VIF 필터링 적용)
    - vif_thresh: float (VIF 임계값)
    - vif_max_iter: int (VIF 반복 최대 횟수)

    Returns:
    - X_train_reduced: pd.DataFrame
    - X_test_reduced: pd.DataFrame or None
    - selected_columns: pd.Index
    """

    # 자동 피처 필터링 및 분석 보고서를 JSON 형태로 생성할 수 있는 함수.
    import json
    from scipy.stats import pearsonr
    # 보고용 구조 초기화
    report = {'cov_corr': [], 'regression': [], 'feature_importance': [], 'vif': []} if return_report else None

    # 분산 기준
    variances = X_train.var()

    # 1. auto-tune: 임계값 없을 때 자동 임계값 산출
    def auto_thresh(series, keep_ratio):
        return series.quantile(1 - keep_ratio)

    vth = variance_thresh
    if auto_tune and vth is None:
        vth = auto_thresh(variances, keep_ratio)
    selected_mask = variances > vth

    # 2. (선택) 공분산, 상관계수 추가 필터
    if use_cov_corr and y_train is not None:
        y_target_series = y_train
        if isinstance(y_train, pd.DataFrame):
            if y_train.shape[1] == 0:
                raise ValueError("feature_filter_auto: y_train is an empty DataFrame.")
            if y_train.shape[1] > 1:
                ensembleForecaster_logger.warning(
                    "feature_filter_auto: y_train is a DataFrame with {} columns. "
                    "Using the first column ('{}') for covariance/correlation calculation with features.".format(
                        y_train.shape[1], y_train.columns[0]
                    )
                )
            y_target_series = y_train.iloc[:, 0]
        elif not isinstance(y_train, pd.Series):
            try:
                temp_series = pd.Series(np.asarray(y_train).ravel())
                if len(temp_series) == X_train.shape[0]:
                    y_target_series = temp_series
                    ensembleForecaster_logger.warning(
                        "feature_filter_auto: y_train was not a pd.Series or pd.DataFrame but was converted to a pd.Series."
                    )
                else:
                    raise ValueError(
                        "feature_filter_auto: y_train is not a pd.Series or pd.DataFrame, and its length "
                        "does not match X_train after attempting conversion."
                    )
            except Exception as e:
                 raise ValueError(
                    f"feature_filter_auto: y_train is not a pd.Series or pd.DataFrame and could not be converted to a 1D Series. Error: {e}"
                )

        covariances = X_train.apply(lambda col: np.cov(col, y_target_series)[0, 1])
        
        # Helper function for safe correlation calculation
        def safe_corrcoef(x_series, y_series):
            if len(x_series) < 2 or len(y_series) < 2:
                return 0.0 # Correlation is undefined for less than 2 points

            x_std = x_series.std()
            y_std = y_series.std()

            # Check for NaN std or near-zero std (constant series)
            if pd.isna(x_std) or x_std < 1e-9 or \
               pd.isna(y_std) or y_std < 1e-9:
                return 0.0
            else:
                # Suppress RuntimeWarning locally as an additional precaution
                with np.errstate(divide='ignore', invalid='ignore'):
                    c = np.corrcoef(x_series, y_series)
                    # np.corrcoef returns a 2x2 matrix; we need the off-diagonal element.
                    # It can also return NaN if inputs are problematic despite std checks.
                    if c.shape == (2,2) and not np.isnan(c[0,1]):
                        return c[0,1]
                    else:
                        return 0.0

        correlations = X_train.apply(lambda col: safe_corrcoef(col, y_target_series))

        cth = covariance_thresh
        if auto_tune and cth is None:
            cth = covariances.abs().quantile(1 - keep_ratio)
        selected_mask &= covariances.abs() > cth

        rth = correlation_thresh
        if auto_tune and rth is None:
            rth = correlations.abs().quantile(1 - keep_ratio)
        selected_mask &= correlations.abs() > rth

    selected_columns = X_train.columns[selected_mask]
    # ✅ VIF 필터링 및 해석
    if use_vif and len(selected_columns) > 0:
        # VIF 값 계산
        df_vif = X_train[selected_columns].astype(float)
        vif_matrix = df_vif.values
        vif_vals = [variance_inflation_factor(vif_matrix, j) for j in range(vif_matrix.shape[1])]
        new_cols = []
        for col, val in zip(selected_columns, vif_vals):
            # 해석 및 비고 설정
            if np.isnan(val):
                interp = '데이터 오류/분산 0 or 완전 중복 (즉시 제거 권고)'
            elif np.isinf(val):
                interp = '절대적 다중공선성 or 정보 없음 (즉시 제거 권고)'
            elif val >= 10:
                interp = '심각한 다중공선성 (변수 제거/차원 축소 권고)'
            elif val >= 5:
                interp = '다중공선성 경계선 (신중히 검토, 유지 가능)'
            else:
                interp = '다중공선성 거의 없음 (안전)'
            # 보고서 기록
            if return_report:
                report['vif'].append({
                    'Feature': col,
                    'VIF': round(val, 2) if not np.isinf(val) and not np.isnan(val) else None,
                    '해석/조치': interp
                })
            # 필터링: NaN/inf/>=10 은 제외
            if not (np.isnan(val) or np.isinf(val) or val >= 10):
                new_cols.append(col)
        selected_columns = pd.Index(new_cols)

    X_train_reduced = X_train[selected_columns]
    X_test_reduced = X_test[selected_columns] if X_test is not None else None
    # 보고용 상관/피어슨 분석 및 중요도
    if return_report and use_cov_corr and y_train is not None:
         y_series = y_train.iloc[:,0] if isinstance(y_train, pd.DataFrame) else pd.Series(y_train)
         n = len(X_train)
         for col in X_train.columns:
             try:
                 corr, p = pearsonr(X_train[col], y_series)
                 # t-value for Pearson correlation: t = r * sqrt((n-2)/(1-r^2))
                 t_val = corr * np.sqrt((n - 2) / (1 - corr**2)) if abs(corr) < 1 else np.inf
             except Exception:
                 corr, p, t_val = 0.0, None, None
             report['cov_corr'].append({
                 'Feature': col,
                 'Type': 'Numeric' if np.issubdtype(X_train[col].dtype, np.number) else 'Categorical',
                 'Corr.(target)': round(corr, 2),
                 't-value': round(t_val, 2) if t_val is not None and np.isfinite(t_val) else None,
                 'p-value': round(p, 4) if p is not None else None,
                 '해석/비고': ('강한' if abs(corr)>0.6 else '중간' if abs(corr)>0.3 else '약한') + ' 상관' if p and p<0.05 else '유의하지 않음'
             })
    # 회귀 계수 분석: 단변량 OLS
    if return_report and use_cov_corr and y_train is not None:
        import statsmodels.api as sm
        for col in X_train.columns:
            try:
                X_col = sm.add_constant(X_train[col])
                model = sm.OLS(y_series, X_col).fit()
                coef = model.params[col]
                se = model.bse[col]
                tval = model.tvalues[col]
                pval = model.pvalues[col]
                # Interpretation and recommendation
                sign = '양의' if coef > 0 else '음의'
                interp = f"부호({ '+' if coef>0 else '-' }): {sign} 방향 영향, 절대값={abs(coef):.2f}"
                if pval < 0.05:
                    rec = 'p-value<0.05: 유의, 변수 유지'
                elif pval < 0.1:
                    rec = 'p-value<0.1: 유의수준 낮음, 유지 검토'
                else:
                    rec = 'p-value>=0.1: 영향 미미, 제거/해석 시 주의'
            except Exception:
                coef, se, tval, pval, interp, rec = None, None, None, None, '분석 실패', ''
            report['regression'].append({
                'Feature': col,
                'Coefficient': round(coef,2) if coef is not None else None,
                'Std.Err': round(se,2) if se is not None else None,
                't-value': round(tval,2) if tval is not None else None,
                'p-value': round(pval,4) if pval is not None else None,
                '해석': interp,
                '조치권고': rec
            })

    if return_report:
        # Feature importance via RandomForest
        rf = RandomForestRegressor(random_state=42)
        rf.fit(X_train[selected_columns], y_series if use_cov_corr and y_train is not None else y_train)
        for col, imp in zip(selected_columns, rf.feature_importances_):
            report['feature_importance'].append({
                'Feature': col,
                'Importance': round(imp, 2),
                '선정/제외 사유': '중요' if imp > np.mean(rf.feature_importances_) else '제외'
            })

    # 보고서 반환 여부
    if return_report:
        return X_train_reduced, X_test_reduced, selected_columns, report
    else:
        return X_train_reduced, X_test_reduced, selected_columns, None

def low_variance_feature_filter(X_train, X_test=None, threshold=0.01):
    """
    분산이 낮은 피처를 제거하고, 동일한 피처만 X_test에도 적용.
    
    Parameters:
    - X_train: pd.DataFrame, 훈련용 특성 데이터
    - X_test: pd.DataFrame or None, 테스트용 특성 데이터 (같은 컬럼 구조여야 함)
    - threshold: float, 분산 임계값

    Returns:
    - X_train_reduced, X_test_reduced, selected_columns
    """
    selector = VarianceThreshold(threshold=threshold)
    selector.fit(X_train)
    
    selected_mask = selector.get_support()
    selected_columns = X_train.columns[selected_mask]
    
    X_train_reduced = X_train[selected_columns]
    
    if X_test is not None:
        X_test_reduced = X_test[selected_columns]
    else:
        X_test_reduced = None

    return X_train_reduced, X_test_reduced, selected_columns

def classify_correlation_level(value):
    """ 상관관계 강도를 Level로 분류하는 함수 """
    if value > 0.6:
        return "Strong"
    elif value > 0.3:
        return "Moderate"
    else:
        return "Weak"



def transform_new_data(df_new, scaler_dict):
    """
    새로운 데이터에 기존 학습된 Scaler를 적용하는 함수.

    Parameters:
        df_new (pd.DataFrame): 변환할 새로운 데이터프레임
        scaler_dict (dict): 기존 학습된 Scaler 객체 딕셔너리

    Returns:
        pd.DataFrame: 변환된 데이터프레임
    """
    transformed_df = df_new.copy()
    for col in scaler_dict:
        scaler = scaler_dict[col]
        transformed_df[col] = scaler.transform(df_new[[col]])
    else:
        print(f"⚠️ Warning: No scaler found for {col}. Skipping transformation.")

    return transformed_df


def save_scalers(scaler_dict, base_dir="scalers", trial_num=None):
    """
    Scaler 객체를 'scalers/trial_숫자/scalers.pkl' 형식으로 저장

    Parameters:
        scaler_dict (dict): 학습된 Scaler 객체가 저장된 딕셔너리
        base_dir (str): 저장할 기본 디렉토리
        trial_num (int or None): trial 번호 지정 (None이면 자동 증가)
    """
    os.makedirs(base_dir, exist_ok=True)

    if trial_num is None:
        # 자동 trial 번호 계산
        existing_trials = [
            int(match.group(1)) for d in os.listdir(base_dir)
            if (match := re.match(r"trial_(\d+)", d)) and os.path.isdir(os.path.join(base_dir, d))
        ]
        trial_num = max(existing_trials, default=0) + 1

    trial_path = os.path.join(base_dir, f"trial_{trial_num}")
    os.makedirs(trial_path, exist_ok=True)

    file_path = os.path.join(trial_path, "scalers.pkl")
    with open(file_path, "wb") as f:
        pickle.dump(scaler_dict, f)


def load_scalers(base_dir="scalers", trial_num=None):
    """
    가장 최근 또는 지정된 trial 디렉토리에서 scalers.pkl 파일 불러오기

    Parameters:
        base_dir (str): 기본 디렉토리
        trial_num (int or None): 특정 trial 번호 (None이면 최신 자동 선택)

    Returns:
        dict: Scaler 객체 딕셔너리
    """
    if not os.path.exists(base_dir):
        raise FileNotFoundError(f"{base_dir} 디렉토리가 존재하지 않습니다.")

    if trial_num is not None:
        trial_path = os.path.join(base_dir, f"trial_{trial_num}")
        if not os.path.exists(trial_path):
            raise FileNotFoundError(f"{trial_path} 디렉토리가 존재하지 않습니다.")
    else:
        # 가장 최신 trial 자동 선택
        existing_trials = [
            (int(match.group(1)), os.path.join(base_dir, d)) for d in os.listdir(base_dir)
            if (match := re.match(r"trial_(\d+)", d)) and os.path.isdir(os.path.join(base_dir, d))
        ]
        if not existing_trials:
            raise FileNotFoundError("저장된 trial_폴더가 없습니다.")
        trial_path = max(existing_trials, key=lambda x: x[0])[1]

    file_path = os.path.join(trial_path, "scalers.pkl")
    with open(file_path, "rb") as f:
        scaler_dict = pickle.load(f)
    return scaler_dict


def feature_optimizer_with_cv(X_train, y_train, model, method="pre", detection_results=None, n_splits=5, scoring="neg_mean_absolute_error"):
    """
    특징 선택 최적화 함수 (튜닝 전/후 적용 가능) + 교차 검증 기능 추가 + 시계열 여부 감지

    Parameters:
        X_train (DataFrame): 입력 특성 데이터
        y_train (Series): 타겟 변수
        model (sklearn model): 사용할 모델 (튜닝 후 특징 선택 시 필요)
        method (str): "pre" - 튜닝 전, "post" - 튜닝 후
        detection_results (dict): 시계열 데이터 여부를 판단하는 사전(dict), 예: {"is_sequential": True}
        n_splits (int): 교차 검증 폴드 수 (기본값: 5)
        scoring (str): sklearn 평가 지표 (기본값: "neg_mean_absolute_error")

    Returns:
        selected_features (list): 선택된 최적 특성 리스트
    """

    # 🚀 교차 검증 방식 자동 선택
    if detection_results is not None and detection_results.get("is_sequential", False):
        spliter = TimeSeriesSplit(n_splits=n_splits) 
    else: 
        spliter = KFold(n_splits=n_splits, shuffle=True)

    if method == "pre":
        # 1️⃣ 다중공선성 기반 특징 제거
        correlation_matrix = X_train.corr().abs()
        upper = correlation_matrix.where(np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool))
        high_correlation_features = [column for column in upper.columns if any(upper[column] > 0.85)]
        X_train = X_train.drop(columns=high_correlation_features, errors='ignore')

        # 2️⃣ RFE 기반 특징 제거 (RandomForest 사용)
        selector = RFE(RandomForestRegressor(n_estimators=400, random_state=42), n_features_to_select=5)
        selector.fit(X_train, y_train)
        selected_features = X_train.columns[selector.support_]

        # 3️⃣ 선택된 특징으로 교차 검증 수행
        scores = cross_val_score(model, X_train[selected_features], y_train, cv=spliter, scoring=scoring)
        print(f"Pre-Tuning CV Score: {np.mean(scores):.4f} ± {np.std(scores):.4f}")

        # 4️⃣ 추가적인 평가 지표(R², MSE, MAE, MAPE, CV(RMSE), NMBE) 분석
        r2_scores, mse_scores, mae_scores, mape_scores, cvrmse_scores, nmbe_scores = [], [], [], [], [], []
        
        for train_idx, test_idx in spliter.split(X_train):
            X_train_fold, X_test_fold = X_train.iloc[train_idx][selected_features], X_train.iloc[test_idx][selected_features]
            y_train_fold, y_test_fold = y_train.iloc[train_idx], y_train.iloc[test_idx]

            model.fit(X_train_fold, y_train_fold)
            y_pred = model.predict(X_test_fold)

            # 평가 지표 계산
            r2_scores.append(r2_score(y_test_fold, y_pred))
            mse_scores.append(mean_squared_error(y_test_fold, y_pred))
            mae_scores.append(mean_absolute_error(y_test_fold, y_pred))
            mape_scores.append(np.mean(np.abs((y_test_fold - y_pred) / y_test_fold)) * 100)
            cvrmse_scores.append(np.sqrt(np.mean((y_test_fold - y_pred) ** 2)) / np.mean(y_test_fold) * 100)
            nmbe_scores.append(np.mean(y_test_fold - y_pred) / np.mean(y_test_fold) * 100)
            
            print(f"R² Score: {np.mean(r2_scores):.4f} ± {np.std(r2_scores):.4f}")
            print(f"MSE: {np.mean(mse_scores):.4f} ± {np.std(mse_scores):.4f}")
            print(f"MAE: {np.mean(mae_scores):.4f} ± {np.std(mae_scores):.4f}")
            print(f"MAPE: {np.mean(mape_scores):.4f} ± {np.std(mape_scores):.4f}")
            print(f"CV(RMSE): {np.mean(cvrmse_scores):.4f} ± {np.std(cvrmse_scores):.4f}")
            print(f"NMBE: {np.mean(nmbe_scores):.4f} ± {np.std(nmbe_scores):.4f}")

            # 5️⃣ 특정 기준을 기반으로 최적의 변수 선택
            # 예: R²가 높고, MAPE와 CV(RMSE)가 낮은 변수 유지
            if np.mean(mape_scores) > 20 or np.mean(cvrmse_scores) > 15:
                print("🚨 높은 MAPE 또는 CV(RMSE) → 추가적인 특징 제거 필요")
                selected_features = selected_features[:-1]  # 중요도가 낮은 변수 추가 제거
                
    elif method == "post" and model is not None:
        pass
    else:
        raise ValueError("Invalid method. Choose 'pre' for pre-tuning optimization or 'post' for post-tuning optimization.")

    return selected_features


def generate_sun_based_cyclic_features(df, lat, lon, mode="day_only"):
    """
    일출/일몰 시간에 맞춰 사인/코사인 변환을 수행하는 함수.
    
    :param df: 원본 데이터프레임 (READ_DATETIME이 인덱스로 설정되어 있어야 함)
    :param lat: 위도
    :param lon: 경도
    :param mode: 'day_only', 'night_only', 'both' 중 선택 (기본값: 'both')
    :return: (일출/일몰 기반 사인/코사인 특징이 추가된 데이터프레임, 추가된 컬럼 리스트)
    """
    if mode not in ["day_only", "night_only", "both"]:
        raise ValueError("mode 값은 'day_only', 'night_only', 'both' 중 하나여야 합니다.")

    df_expanded = df.copy()

    # ✅ index의 시간대를 'Asia/Seoul'로 설정 (tz-naive → tz-aware)
    if df_expanded.index.tz is None:
        df_expanded.index = df_expanded.index.tz_localize("Asia/Seoul")
    else:
        df_expanded.index = df_expanded.index.tz_convert("Asia/Seoul")

    # ✅ 날짜별 일출/일몰 시간 계산
    df_expanded["sunrise"] = [get_sunrise_sunset(lat, lon, date)[0] for date in df_expanded.index.date]
    df_expanded["sunset"] = [get_sunrise_sunset(lat, lon, date)[1] for date in df_expanded.index.date]

    # ✅ 낮(일출~일몰)인지 여부 (tz-aware 데이터 비교 가능)
    df_expanded["is_daytime"] = ((df_expanded.index >= df_expanded["sunrise"]) & 
                                  (df_expanded.index <= df_expanded["sunset"]))

    # ✅ 낮/밤 시간을 일출-일몰 주기에 맞춰 정규화
    def normalize_time(timestamp, sunrise, sunset):
        if sunrise <= timestamp <= sunset:
            # 낮 시간 정규화 (0 ~ π)
            return np.pi * (timestamp - sunrise).total_seconds() / (sunset - sunrise).total_seconds()
        else:
            # 밤 시간 정규화 (π ~ 2π)
            next_sunrise = get_sunrise_sunset(lat, lon, (timestamp + pd.Timedelta(days=1)).date())[0]
            return np.pi + np.pi * (timestamp - sunset).total_seconds() / (next_sunrise - sunset).total_seconds()

    df_expanded["normalized_time"] = [normalize_time(ts, sr, ss) for ts, sr, ss in 
                                      zip(df_expanded.index, df_expanded["sunrise"], df_expanded["sunset"])]

    # ✅ 선택한 mode에 따라 사인/코사인 변환
    added_columns = ["is_daytime"]
    
    if mode == "day_only":
        df_expanded["sun_sin"] = np.where(df_expanded["is_daytime"], np.sin(df_expanded["normalized_time"]), 0)
        added_columns.append("sun_sin")

    elif mode == "night_only":
        df_expanded["sun_sin"] = np.where(~df_expanded["is_daytime"], np.sin(df_expanded["normalized_time"]), 0)
        added_columns.append("sun_sin")

    elif mode == "both":
        df_expanded["sun_sin"] = np.sin(df_expanded["normalized_time"])
        df_expanded["sun_cos"] = np.cos(df_expanded["normalized_time"])
        added_columns.extend(["sun_sin", "sun_cos"])

    # 불필요한 컬럼 제거
    df_expanded.drop(columns=["sunrise", "sunset", "normalized_time"], inplace=True)

    ensembleForecaster_logger.info(f"일출/일몰 시간에 맞춰 사인/코사인 변환 생성 : {added_columns}")
    
    nan_columns = df_expanded.columns[df_expanded.isna().all()].tolist()
    ensembleForecaster_logger.debug(f"NaN만 포함된 컬럼: {nan_columns}")
    
    return df_expanded, added_columns

def add_peak_features(raw_data, target_columns, detection_results, ref_interval=5, peak_threshold=2.0):
    """
    피크 감지 결과를 활용하여 추가적인 피크 관련 변수를 생성하는 함수.

    Parameters:
        raw_data (pd.DataFrame): 원본 데이터프레임
        target (str): 피크 감지를 수행할 대상 컬럼명
        detection_results (dict): 탐지된 패턴 결과
        ref_interval (int): 데이터의 기준 시간 간격 (분 단위, 기본값 5분)

    Returns:
        pd.DataFrame: 변환된 데이터프레임 (새로운 피크 관련 변수 포함)
        list: 추가된 특징 컬럼 리스트
    """
    
    df_expanded = raw_data.copy()
    added_features = []

    for target in target_columns:
        # ✅ 탐지된 피크 여부 확인
        has_multiscale_features = detection_results[target].get("has_multiscale_features", False)
        has_peak_features = detection_results[target].get("has_peak_features", False)

        # ✅ 피크가 감지된 경우에만 피처 생성
        if has_peak_features or has_multiscale_features:
            
            # ✅ detection_results에 저장된 피크 인덱스를 활용한 마스크 생성
            peak_indices = detection_results[target].get("peak_indices", [])
            peak_ind = df_expanded.index.to_series().isin(peak_indices).astype(int)
            df_expanded[f"{target}_peak_indicator"] = peak_ind
            added_features.append(f"{target}_peak_indicator")
             # window definitions
            windows = {
                "ultra_short": int(0.5 * (60 / ref_interval)),
                "short": int(1 * (60 / ref_interval)),
                "long": int(3 * (60 / ref_interval))
            }
            for name, w in windows.items():
                # intensity mean, count, rate change, duration
                df_expanded[f"{target}_peak_intensity_mean_{name}"] = df_expanded[target].where(peak_ind == 1).rolling(window=w, min_periods=1).mean()
                df_expanded[f"{target}_peak_count_{name}"] = peak_ind.rolling(window=w, min_periods=1).sum().astype(int)
                df_expanded[f"{target}_peak_rate_change_{name}"] = df_expanded[f"{target}_peak_count_{name}"].diff().fillna(0).astype(int)
                df_expanded[f"{target}_peak_duration_{name}"] = peak_ind.groupby((peak_ind != peak_ind.shift()).cumsum()).cumsum()
                added_features += [
                     f"{target}_peak_intensity_mean_{name}", f"{target}_peak_count_{name}",
                     f"{target}_peak_rate_change_{name}", f"{target}_peak_duration_{name}"
                 ]
            df_expanded[f"{target}_cumulative_peak_count"] = peak_ind.cumsum().astype(int)
            df_expanded[f"{target}_time_since_last_peak"] = peak_ind.cumsum().diff().fillna(0).astype(int)
            added_features += [f"{target}_cumulative_peak_count", f"{target}_time_since_last_peak"]
            # peak trend from ultra-short intensity
            df_expanded[f"{target}_peak_trend"] = df_expanded[f"{target}_peak_intensity_mean_ultra_short"].diff().fillna(0).apply(lambda x: 1 if x>0 else 0)
            added_features.append(f"{target}_peak_trend")

    ensembleForecaster_logger.info(f"피크 관련 변수를 생성 : {added_features}")
    
    nan_columns = df_expanded.columns[df_expanded.isna().all()].tolist()
    ensembleForecaster_logger.debug(f"NaN만 포함된 컬럼: {nan_columns}")
    
    return df_expanded, added_features


# 쾌적지수 계산 함수
def discomfort_index(temp, hum):
    """
    온도와 습도를 기반으로 쾌적지수를 계산합니다.

    쾌적지수는 열과 습도로 인해 인간이 경험하는 불쾌감을 추정하는 데 사용되는 지표입니다.

    매개변수:
    temp (float): 섭씨 온도.
    hum (float): 상대 습도 (0에서 100 사이의 백분율).

    반환값:
    float: 계산된 쾌적지수.
    """
    return 0.81 * temp + 0.01 * hum * (0.99 * temp - 14.3) + 46.3

def mapping_sensor_variables(raw_data):
    """
    센서 변수명을 기반으로 자동으로 실내/외, 센서 종류(온도/습도/CO2)로 맵핑하는 함수

    Parameters:
        var_dict (dict): {변수명: 태그값} 형식의 딕셔너리

    Returns:
        list of dict: 자동 분류된 센서 정보 리스트
    """
