from statsmodels.tsa.stattools import pacf
import numpy as np
import warnings

# data는 시계열 데이터 (numpy array 또는 pandas Series)
# requested_nlags는 사용자가 요청한 nlags 값
def calculate_pacf_safely(data, requested_nlags):
    n_samples = len(data)
    
    # 샘플 크기의 50%를 최대 nlags로 설정 (단, 최소 1 이상)
    # 일반적으로 pacf 함수 자체에서 nlags의 기본 최대값을 n_samples // 2 - 1 등으로 제한하기도 합니다.
    # statsmodels의 pacf는 기본적으로 min(n_samples // 2 - 1, 40) 정도를 사용하거나, 사용자가 지정한 nlags를 사용합니다.
    # 여기서는 명시적으로 50% 제한을 두겠습니다.
    max_permissible_nlags = max(1, n_samples // 2 -1) # -1은 보수적인 접근

    actual_nlags = requested_nlags
    
    if requested_nlags >= max_permissible_nlags:
        warnings.warn(
            f"Requested nlags {requested_nlags} is too large for sample size {n_samples}. "
            f"Adjusting nlags to {max_permissible_nlags}.",
            UserWarning
        )
        actual_nlags = max_permissible_nlags
        
    if actual_nlags <= 0 and n_samples > 1 : # 최소한의 lag는 1이 되도록 (샘플이 2개 이상일때)
        actual_nlags = 1
    elif n_samples <=1: # 샘플이 너무 적어 PACF 계산 불가
        warnings.warn(
            f"Sample size {n_samples} is too small to compute PACF.",
            UserWarning
        )
        return np.array([]) # 빈 배열 또는 적절한 값 반환

    try:
        # method='ywm' 또는 'ols' 등 상황에 맞는 메서드 사용
        pacf_values = pacf(data, nlags=actual_nlags, method='ywm') 
        return pacf_values
    except ValueError as e:
        warnings.warn(f"Error computing PACF even after adjusting nlags: {e}", UserWarning)
        return np.array([]) # 오류 발생 시 빈 배열 또는 적절한 값 반환

# 사용 예시
# some_time_series_data = [...] 
# user_defined_nlags = 30
# pacf_results = calculate_pacf_safely(some_time_series_data, user_defined_nlags)
# if pacf_results.size > 0:
#     # PACF 결과 사용
# else:
#     # PACF 계산 실패 처리

import numpy as np
import holidays  # 대한민국의 공휴일 정보를 데이터프레임에 추가
import pandas as pd
from statsmodels.tsa.stattools import adfuller, acf, pacf
from scipy.stats import skew, kurtosis, shapiro, zscore
from scipy.stats.mstats import winsorize
from sklearn.cluster import DBSCAN
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, MaxAbsScaler, QuantileTransformer, PowerTransformer
from utils.AI.ensemble_forecaster.config import ensembleForecaster_logger

import numpy as np
from scipy.stats import shapiro, anderson, normaltest

def get_normality_pvalue(data: np.ndarray) -> float:
    data = data.flatten()
    N = len(data)

    if N <= 50:
        _, p = shapiro(data)
    elif N <= 300:
        result = anderson(data)
        # Anderson은 p-value를 반환하지 않음, 임계값 기반 추정 (임의 기준 5% 사용)
        p = 0.05 if result.statistic > result.critical_values[2] else 0.1
    else:
        _, p = normaltest(data)

    return p

def classify_correlation_level(value):
    """ 상관관계 강도를 Level로 분류하는 함수 """
    if value > 0.6:
        return "Strong"
    elif value > 0.3:
        return "Moderate"
    else:
        return "Weak"


def detect_time_series_patterns(
    raw_data: pd.DataFrame,
    target_columns=None,
    max_lag=30,  # 288 = 24시간 * 12 (5분 간격)
    ref_interval=5,
    peak_threshold=2.0,
):
    """
    시계열 데이터에서 다양한 패턴(정렬, 시간 의존성, 주기성, 노이즈, 이상치, 결측치, 트렌드, 변화 등)을 탐지하는 함수.
    Lag(시차) feature가 필요한지와 적절한 lag 추천까지 포함.
    다중 컬럼 동시 지원.
    로그는 ensembleForecaster_logger에 기록됨.
    """

    # === 로그 함수: ensembleForecaster_logger로 고정 ===
    def log(msg, level='info'):
        import builtins
        if 'ensembleForecaster_logger' in globals():
            logger = globals()['ensembleForecaster_logger']
        else:
            # 없는 경우 print fallback (주로 테스트/디버깅용)
            logger = None
        if logger:
            if hasattr(logger, level):
                getattr(logger, level)(msg)
            else:
                logger.info(msg)
        else:
            builtins.print(msg)

    if target_columns is None:
        target_columns = raw_data.select_dtypes(include=[np.number]).columns.tolist()

    detection_results = {}

    # 1. 시계열 데이터 정렬 여부 (순차성)
    detection_results["is_sequential"] = raw_data.index.is_monotonic_increasing
    log(f"데이터가 시간 순서대로 정렬됨: {detection_results['is_sequential']}")

    # 2. 시간 의존성
    has_temporal_dependency = (raw_data.index.to_series().diff().dt.total_seconds().fillna(0) > 0).any()
    detection_results["has_temporal_dependency"] = has_temporal_dependency
    log(f"데이터가 시간 흐름에 의존함: {has_temporal_dependency}")

    # 3. 결측치 탐지
    detection_results["has_missing_values"] = raw_data.isnull().any().any()
    log(f"데이터에 결측치 존재 여부: {detection_results['has_missing_values']}")

    for target in target_columns:
        detection_results[target] = {}

        # 4. 노이즈(이상치) 탐지
        try:
            window_size = max(1, int(60 / ref_interval))
            rolling_mean = raw_data[target].rolling(window=window_size, min_periods=1).mean()
            noise_mask = np.abs(raw_data[target] - rolling_mean) > rolling_mean.std()
            detection_results[target]["is_noisy"] = noise_mask.any()
            log(f"{target} 데이터에 노이즈(이상치) 존재 여부: {detection_results[target]['is_noisy']}")
        except Exception as err:
            detection_results[target]["is_noisy"] = False
            log(f"{target} 컬럼이 없어 노이즈 감지를 수행할 수 없습니다. {err}", level="warning")

        # 5. 트렌드 및 항상 증가 여부
        try:
            detection_results[target]["has_trend"] = raw_data[target].diff().fillna(0).cumsum().iloc[-1] > 0
            detection_results[target]["is_always_increasing"] = raw_data[target].diff().dropna().ge(0).all()
            log(f"{target} 데이터가 트렌드를 가지는지 확인: {detection_results[target]['has_trend']}")
            log(f"{target} 데이터가 항상 증가하는 형태인지 확인: {detection_results[target]['is_always_increasing']}")
        except Exception as err:
            detection_results[target]["has_trend"] = False
            detection_results[target]["is_always_increasing"] = False
            log(f"{target} 컬럼이 없어 트렌드 감지를 수행할 수 없습니다. {err}", level="warning")

        # 6. 단기적/장기적 변화, 피크(급격변동) 탐지
        try:
            ultra_short_window = int(0.5 * (60 / ref_interval))
            short_window = int(1 * (60 / ref_interval))
            long_window = int(3 * (60 / ref_interval))

            ultra_short_term_trend = raw_data[target].diff().abs().rolling(window=ultra_short_window, min_periods=1).mean()
            short_term_trend = raw_data[target].diff().abs().rolling(window=short_window, min_periods=1).mean()
            long_term_trend = raw_data[target].diff().abs().rolling(window=long_window, min_periods=1).mean()

            detection_results[target]["has_multiscale_features"] = (
                (ultra_short_term_trend > 0).any() and
                (short_term_trend > 0).any() and
                (long_term_trend > 0).any()
            )

            value_diff = raw_data[target].diff().fillna(0)
            value_pct_change = raw_data[target].pct_change().fillna(0)
            rolling_mean = raw_data[target].rolling(window=short_window, min_periods=1).mean()
            rolling_std = raw_data[target].rolling(window=short_window, min_periods=1).std().fillna(0)

            # 피크(급격변동) 탐지
            peak_indicator = (
                (value_diff.abs() > rolling_std * peak_threshold) |
                (value_pct_change.abs() > rolling_std * peak_threshold) |
                (ultra_short_term_trend > rolling_std * peak_threshold)
            ).astype(int)

            detection_results[target]["has_peak_features"] = int(peak_indicator.sum()) > 0
            detection_results[target]["peak_count"] = int(peak_indicator.sum())
            detection_results[target]["peak_indices"] = list(raw_data.index[peak_indicator == 1])

            log(f"{target}: 피크(급격변동) 개수: {detection_results[target]['peak_count']}")
            log(f"{target}: 초단기, 단기, 장기 변화량 기반 피크 감지 결과: {detection_results[target]['has_peak_features']}")

        except Exception as err:
            detection_results[target]["has_multiscale_features"] = False
            detection_results[target]["has_peak_features"] = False
            detection_results[target]["peak_count"] = 0
            detection_results[target]["peak_indices"] = []
            log(f"{target} 컬럼이 없어 단기/장기 변화 또는 피크 감지를 수행할 수 없습니다. {err}", level="warning")

        # 7. Lag(시차) 관련 Feature 필요성 및 추천 (ADF 제거됨)
        target_data_dropna = raw_data[target].dropna()
        n_samples_acf = len(target_data_dropna)
        actual_nlags_acf = min(max_lag, n_samples_acf - 1) if n_samples_acf > 1 else 0
        if actual_nlags_acf > 0:
            acf_values = acf(target_data_dropna, nlags=actual_nlags_acf)
        else:
            acf_values = np.array([])
            log(f"[{target}] 샘플 크기가 너무 작아 ACF를 계산할 수 없습니다: {n_samples_acf}", level="warning")

        n_samples_pacf = len(target_data_dropna)
        max_permissible_nlags_pacf = max(1, n_samples_pacf // 2 - 1) if n_samples_pacf > 3 else 0
        actual_nlags_pacf = max_lag
        if max_lag >= max_permissible_nlags_pacf and max_permissible_nlags_pacf > 0:
            warnings.warn(
                f"Requested nlags {max_lag} for PACF is too large for sample size {n_samples_pacf}. "
                f"Adjusting nlags to {max_permissible_nlags_pacf}.",
                UserWarning
            )
            log(f"[{target}] PACF 계산 시 요청된 nlags({max_lag})가 샘플 크기({n_samples_pacf})에 비해 너무 큽니다. nlags를 {max_permissible_nlags_pacf}로 조정합니다.", level="warning")
            actual_nlags_pacf = max_permissible_nlags_pacf
        elif max_permissible_nlags_pacf == 0:
            warnings.warn(
                f"Sample size {n_samples_pacf} is too small to compute PACF with requested max_lag {max_lag}. Setting nlags for PACF to 0.",
                UserWarning
            )
            log(f"[{target}] 샘플 크기({n_samples_pacf})가 너무 작아 PACF를 계산할 수 없습니다. PACF nlags를 0으로 설정합니다.", level="warning")
            actual_nlags_pacf = 0
        if actual_nlags_pacf > 0:
            try:
                pacf_values = pacf(target_data_dropna, nlags=actual_nlags_pacf, method='ywm')
            except ValueError as e:
                log(f"[{target}] PACF 계산 중 오류 발생 (nlags={actual_nlags_pacf}, samples={n_samples_pacf}): {e}", level="error")
                pacf_values = np.array([])
        else:
            pacf_values = np.array([])

        significant_acf_lags = np.where(acf_values > 0.2)[0] if acf_values.size > 0 else []
        strong_acf_lags = np.where(acf_values > 0.6)[0] if acf_values.size > 0 else []
        significant_pacf_lags_indices = np.where(pacf_values > 0.2)[0] if pacf_values.size > 0 else []
        strong_pacf_lags_indices = np.where(pacf_values > 0.6)[0] if pacf_values.size > 0 else []

        detection_results[target]["significant_lags"] = list(strong_pacf_lags_indices)
        detection_results[target]["has_strong_periodicity"] = (len(strong_acf_lags) > 0 or len(strong_pacf_lags_indices) > 0)
        detection_results[target]["lag_needed"] = len(significant_pacf_lags_indices) > 0

        # 8. 주기성 및 달력 기반 패턴
        try:
            detection_results[target]["has_periodicity"] = raw_data.index.freq is not None
            detection_results[target]["has_daily_pattern"] = raw_data.index.hour.value_counts(normalize=True).max() > 0.2
            detection_results[target]["has_weekly_pattern"] = raw_data.index.dayofweek.value_counts(normalize=True).max() > 0.2
            detection_results[target]["has_monthly_pattern"] = raw_data.index.day.value_counts(normalize=True).max() > 0.1
            detection_results[target]["has_quarterly_pattern"] = raw_data.index.month.isin([3, 6, 9, 12]).mean() > 0.2

            raw_data['day_of_week'] = raw_data.index.dayofweek
            raw_data['is_weekend'] = (raw_data['day_of_week'] >= 5).astype(int)
            detection_results[target]["has_rest_day_effect"] = raw_data["is_weekend"].mean() > 0.1

            kr_holidays = holidays.KR()
            raw_data['is_holiday'] = raw_data.index.to_series().apply(lambda x: 1 if x in kr_holidays else 0)
            detection_results[target]["has_holiday_effect"] = raw_data["is_holiday"].mean() > 0.1
            detection_results[target]["has_rest_day_pattern"] = (
                raw_data["is_holiday"].mean() > 0.10 and raw_data["is_weekend"].mean() > 0.10
            )
            detection_results[target]["has_holiday_shift"] = (
                raw_data["is_weekend"].shift(1).corr(raw_data[target]) > 0.2 or
                raw_data["is_holiday"].shift(1).corr(raw_data[target]) > 0.2
            )
        except Exception as err:
            detection_results[target]["has_periodicity"] = False
            detection_results[target]["has_daily_pattern"] = False
            detection_results[target]["has_weekly_pattern"] = False
            detection_results[target]["has_monthly_pattern"] = False
            detection_results[target]["has_quarterly_pattern"] = False
            detection_results[target]["has_rest_day_effect"] = False
            detection_results[target]["has_holiday_effect"] = False
            detection_results[target]["has_rest_day_pattern"] = False
            detection_results[target]["has_holiday_shift"] = False
            log(f"{target} 컬럼에서 주기성/달력 패턴 탐지 중 오류: {err}", level="warning")

        # 9. 집계 유형 Feature 추천
        try:
            series_hourly = raw_data[target].resample('1h').agg(['mean', 'median', 'min', 'max', 'std', 'sum']).dropna()
            std_dev = series_hourly.std()
            iqr_value = np.percentile(series_hourly, 75) - np.percentile(series_hourly, 25)
            skewness = series_hourly.apply(skew)
            kurt = series_hourly.apply(kurtosis)
            q1 = np.percentile(series_hourly, 25)
            q3 = np.percentile(series_hourly, 75)
            outlier_ratio = ((series_hourly < (q1 - 1.5 * iqr_value)) | (series_hourly > (q3 + 1.5 * iqr_value))).mean()
            rolling_mean_diff = series_hourly.rolling(window=5, min_periods=1).mean().diff().abs().mean()
            acf_values_hourly = acf(series_hourly['mean'], nlags=24)
            pacf_values_hourly = pacf(series_hourly['mean'], nlags=24)
            hourly_pattern = np.where(acf_values_hourly > 0.5)[0]
            daily_pattern = np.where(acf_values_hourly > 0.7)[0]
            recommended_lags = sorted([lag for lag in set(hourly_pattern) | set(daily_pattern) if lag > 0])

            recommended_aggregations = []
            if outlier_ratio.mean() > 0.1:
                recommended_aggregations.append("median")
            if rolling_mean_diff.mean() > std_dev.mean() * 0.5:
                recommended_aggregations.append("rolling_mean")
            if len(recommended_aggregations) == 0:
                recommended_aggregations.append("mean")

            detection_results[target]["recommended_aggregations"] = recommended_aggregations
            detection_results[target]["recommended_lags"] = recommended_lags
            detection_results[target]["strong_pacf_lags"] = list(np.where(pacf_values_hourly > 0.6)[0])
            detection_results[target]["significant_pacf_lags"] = list(np.where(pacf_values_hourly > 0.2)[0])
            detection_results[target]["std_dev"] = std_dev.to_dict()
            detection_results[target]["skewness"] = skewness.to_dict()
            detection_results[target]["kurtosis"] = kurt.to_dict()
            detection_results[target]["outlier_ratio"] = outlier_ratio.to_dict()
            detection_results[target]["rolling_mean_diff"] = rolling_mean_diff.to_dict()
        except Exception as e:
            detection_results[target]["error"] = str(e)
            detection_results[target]["recommended_aggregations"] = ["unknown"]

    return detection_results


def handle_missing_values(df, method="interpolate", fill_value=None, threshold=0.1):
    """
    결측치 처리 함수
    :param df: 처리할 데이터프레임
    :param method: 결측치 처리 방법 ('drop', 'ffill', 'bfill', 'mean', 'median', 'mode', 'fill', 'interpolate', 'polynomial', 'spline')
    :param fill_value: 특정 값으로 채울 경우 사용
    :param threshold: 결측치 비율이 특정 값 이상인 열 제거 기준
    :return: 결측치가 처리된 데이터프레임
    """
    missing_ratio = df.isnull().mean()
    
    # 결측치 비율이 특정 threshold 이상인 열 삭제
    high_missing_cols = missing_ratio[missing_ratio > threshold].index
    if len(high_missing_cols) > 0:
        print(f"⚠️ Warning: High missing ratio detected in columns: {list(high_missing_cols)} → Dropped")
        df = df.drop(columns=high_missing_cols)

    # 결측치 처리 방법 적용
    if method == "drop":
        df = df.dropna()
    elif method == "ffill":
        df = df.ffill()
    elif method == "bfill":
        df = df.bfill()
    elif method == "mean":
        df = df.fillna(df.mean())
    elif method == "median":
        df = df.fillna(df.median())
    elif method == "mode":
        df = df.fillna(df.mode().iloc[0])
    elif method == "fill":
        df = df.fillna(fill_value)
    elif method == "interpolate":
        df = df.interpolate(method='linear', limit_direction='both')
    elif method == "polynomial":
        df = df.interpolate(method='polynomial', order=2, limit_direction='both')
    elif method == "spline":
        df = df.interpolate(method='spline', order=2, limit_direction='both')
    
    return df

def generate_lag_features(df_no_outliers, target_columns, lag_results, target_df=None):
    """
    탐지된 Lag 정보를 반영하여 Moderate 및 Strong 수준의 Lag 변수만 생성
    
    :param df_no_outliers: 이상치 제거된 DataFrame
    :param target_columns: 예측 대상이 되는 컬럼 리스트
    :param lag_results: 탐지된 Lag 결과 (상관관계 강도 포함)
    :param target_df: 미래 예측을 위한 별도의 대상 DataFrame (기본값: None)
    :return: (Lag 변수가 추가된 DataFrame, 추가된 lag 컬럼 리스트)
    """
    added_lag_columns = []
    for target in target_columns:
        if not target in lag_results:
            ensembleForecaster_logger.debug(f"탐지된 {target} Lag 정보가 없는 경우 무시")
            continue  # 탐지된 Lag 정보가 없는 경우 무시
    
        selected_lags = lag_results[target]["recommended_lags"]
        if not selected_lags:
            ensembleForecaster_logger.debug("유의미한 {target} Lag이 없으면 건너뜀")
            continue  # 유의미한 Lag이 없으면 건너뜀
        if target_df is not None:
            # target_df 기반으로 lag 변수 생성
            future_data = df_no_outliers.copy()
            for lag in selected_lags:
                lag_column = f"{target}_lag_{lag}"
                future_data[lag_column] = target_df[target].shift(int(lag))
                added_lag_columns.append(lag_column)
            future_data.dropna(inplace=True)
            return future_data, added_lag_columns  # target_df 기반 생성 시 반환

        # 기존 df_no_outliers에서 lag 변수 생성
        for lag in selected_lags:
            lag_column = f"{target}_lag_{lag}"
            df_no_outliers[lag_column] = df_no_outliers[target].shift(int(lag))
            added_lag_columns.append(lag_column)

    df_no_outliers.dropna(inplace=True)  # 결측치 제거
    # ✅ 7. NaN만 포함된 컬럼 확인 후 제거
    nan_columns = df_no_outliers.columns[df_no_outliers.isna().all()].tolist()
    if nan_columns:
        ensembleForecaster_logger.info(f"🚨 NaN만 포함된 컬럼 제거: {nan_columns}")
        df_no_outliers = df_no_outliers.drop(columns=nan_columns)
        added_lag_columns = [col for col in added_lag_columns if col not in nan_columns]  # 추가된 컬럼에서 제거
        
    ensembleForecaster_logger.info(f"[{target}] 적용된 lag 변수: {added_lag_columns}")
    
    return df_no_outliers, added_lag_columns

def optimize_outlier_removal(raw_data, target_columns=None, max_iterations=2, noise_threshold=0.02, 
                             threshold=0.05, method="iqr", max_removal_ratio=0.05, winsorize_limits=[0.05, 0.05]):
    """
    이상치 제거를 최적화하는 함수.
    - 여러 개의 `value` 컬럼을 지원
    - 제거된 데이터 비율이 설정한 값(기본 5%)을 초과하면 경고 발생
    - LOF(Local Outlier Factor) 중복 값 문제 해결을 위해 `n_neighbors=30` 설정
    
    Parameters:
        raw_data (pd.DataFrame): 이상치 제거할 데이터프레임
        target_columns (list): 이상치를 제거할 컬럼 리스트 (기본: 모든 수치형 컬럼)
        max_iterations (int): 최대 반복 횟수
        noise_threshold (float): 노이즈 비율이 이 값 이하가 되면 중지
        threshold (float): 이상치 제거 비율이 이 값 이상이면 경보 발생 (기본값 5%)
        method (str): 이상치 제거 방법 ("rolling_mean", "iqr", "zscore", "winsorizing", "lof", "dbscan")
        max_removal_ratio (float): 한 번에 제거 가능한 최대 비율 (기본값 5%)
        winsorize_limits (list): Winsorizing 적용 범위 (기본값 [0.05, 0.05])

    Returns:
        pd.DataFrame: 이상치가 최적 제거된 데이터프레임
    """
    
    if target_columns is None:
        target_columns = raw_data.select_dtypes(include=[np.number]).columns.tolist()

    initial_count = len(raw_data)  # 초기 데이터 개수
    initial_raw_data = raw_data.copy()  # 원본 데이터 복사

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        removed_rows = 0

        for col in target_columns:
            before_removal_count = len(raw_data)

            if method == "iqr":
                # IQR 기반 제거 (범위를 더 완화)
                Q1 = raw_data[col].quantile(0.10)  # 기존 0.25 → 완화
                Q3 = raw_data[col].quantile(0.90)  # 기존 0.75 → 완화
                IQR = Q3 - Q1
                mask = (raw_data[col] >= (Q1 - 1.0 * IQR)) & (raw_data[col] <= (Q3 + 1.0 * IQR))

            elif method == "zscore":
                # Z-score 기반 제거 (임계값 조정)
                z_scores = zscore(raw_data[col].dropna())
                mask = np.abs(z_scores) <= 2.5  # 기존 3 → 완화

            elif method == "rolling_mean":
                # Rolling Mean 기반 제거
                rolling_mean = raw_data[col].rolling(window=7, min_periods=1).mean()  # 기존 5 → 7
                std_dev = rolling_mean.std()
                mask = np.abs(raw_data[col] - rolling_mean) <= std_dev * 1.5  # 기존 1.0 → 완화

            elif method == "winsorizing":
                # Winsorizing (극단값 대체)
                raw_data[col] = winsorize(raw_data[col], limits=winsorize_limits)
                continue  # 데이터 변환이므로 삭제 필요 없음

            elif method == "lof":
                # LOF 기반 이상치 탐지 (n_neighbors 증가)
                lof = LocalOutlierFactor(n_neighbors=30)
                lof_labels = lof.fit_predict(raw_data[[col]])
                mask = lof_labels != -1  # LOF에서 -1은 이상치

            elif method == "dbscan":
                # DBSCAN 기반 이상치 탐지
                db = DBSCAN(eps=0.8, min_samples=10).fit(raw_data[[col]])  # 기존 eps=0.5, min_samples=5 → 완화
                mask = db.labels_ != -1  # DBSCAN에서 -1은 이상치

            else:
                raise ValueError("지원되지 않는 method입니다. ('iqr', 'zscore', 'rolling_mean', 'winsorizing', 'lof', 'dbscan' 중 선택)")


            # 이상치 제거 적용
            raw_data = raw_data[mask]
            removed_rows += before_removal_count - len(raw_data)

        # 이상치 제거 비율 계산
        removed_ratio = removed_rows / initial_count

        # 한 번에 너무 많은 데이터가 삭제되면 경고 및 원본 복구
        if removed_ratio > max_removal_ratio:
            ensembleForecaster_logger.warning(f"⚠️ {method} 이상치 제거 비율이 {removed_ratio:.2%}로 {max_removal_ratio:.2%} 초과! 원본 데이터로 복구합니다. ⚠️")
            return raw_data.copy() if removed_rows == 0 else initial_raw_data.copy()

        if removed_ratio < noise_threshold:
            ensembleForecaster_logger.info(f"{method} 노이즈 비율 {removed_ratio:.2%} 이하로 감소, 이상치 제거 최적화 완료")
            break
    ensembleForecaster_logger.info(f"{method} 이상치 최적화 완료 ✅")
    return raw_data


def generate_autocorrelation_features(raw_data, target_columns, detect_results):
    """
    탐지된 패턴을 기반으로 Sin/Cos 변환을 자동 적용하는 함수.

    Parameters:
        raw_data (pd.DataFrame): 원본 데이터프레임 (datetime index 필요)
        detect_results (dict): 탐지된 패턴 결과

    Returns:
        pd.DataFrame: 변환된 데이터프레임
        list: 추가된 특징 컬럼 리스트
    """
    added_columns = []
    additional_features = {}  # 여러 컬럼을 임시로 담아둠
    
    # 공통 holiday/weekend feature, 한 번만 계산 (모든 타겟 공통적용 시)
    idx = raw_data.index
    kr_holidays = holidays.KR()
    is_holiday = idx.to_series().apply(lambda x: 1 if x in kr_holidays else 0)
    day_of_week = idx.dayofweek
    is_weekend = (day_of_week >= 5).astype(int)
    
    # 1. 하루 단위
    if all(detect_results[target].get("has_daily_pattern", False) for target in target_columns):
        additional_features["hour"] = idx.hour
        additional_features["minute"] = idx.minute
        additional_features["time_of_day"] = idx.hour * 60 + idx.minute
        added_columns += ["hour", "minute", "time_of_day"]
        
    # 2. 주 단위
    if all(detect_results[target].get("has_weekly_pattern", False) for target in target_columns):
        additional_features["day_of_week"] = day_of_week
        additional_features["is_weekend"] = is_weekend
        added_columns += ["day_of_week", "is_weekend"]

    # 3. 월 단위
    if all(detect_results[target].get("has_monthly_pattern", False) for target in target_columns):
        additional_features["month"] = idx.month
        additional_features["is_month_start"] = idx.is_month_start.astype(int)
        additional_features["is_month_end"] = idx.is_month_end.astype(int)
        additional_features["day_of_month"] = idx.day
        added_columns += ["month", "is_month_start", "is_month_end", "day_of_month"]
        
    # 4. 분기 단위
    if all(detect_results[target].get("has_quarterly_pattern", False) for target in target_columns):
        additional_features["quarter"] = idx.quarter
        added_columns += ["quarter"]
    
    for target in target_columns:
        # 1. 하루 단위 패턴이 있는 경우 → 하루 단위 sin/cos 변환 추가
        if detect_results[target].get("has_daily_pattern", False):
            additional_features[f"{target}_hour_sin"] = np.sin(2 * np.pi * idx.hour / 24)
            additional_features[f"{target}_hour_cos"] = np.cos(2 * np.pi * idx.hour / 24)
            added_columns += [f"{target}_hour_sin", f"{target}_hour_cos"]

        # 2. 주 단위 패턴이 있는 경우 → 주 단위 sin/cos 변환 추가
        if detect_results[target].get("has_weekly_pattern", False):
            additional_features[f"{target}_week_sin"] = np.sin(2 * np.pi * day_of_week / 7)
            additional_features[f"{target}_week_cos"] = np.cos(2 * np.pi * day_of_week / 7)
            added_columns += [f"{target}_week_sin", f"{target}_week_cos"]

        # 3. 월 단위 패턴이 있는 경우 → 월 단위 sin/cos 변환 추가
        if detect_results[target].get("has_monthly_pattern", False):
            additional_features[f"{target}_month_sin"] = np.sin(2 * np.pi * idx.month / 12)
            additional_features[f"{target}_month_cos"] = np.cos(2 * np.pi * idx.month / 12)
            added_columns += [f"{target}_month_sin", f"{target}_month_cos"]

        # 4. 분기 단위 패턴이 있는 경우 → 분기 단위 sin/cos 변환 추가
        if detect_results[target].get("has_quarterly_pattern", False):
            additional_features[f"{target}_quarter_sin"] = np.sin(2 * np.pi * idx.quarter / 4)
            additional_features[f"{target}_quarter_cos"] = np.cos(2 * np.pi * idx.quarter / 4)
            added_columns += [f"{target}_quarter_sin", f"{target}_quarter_cos"]

        # ✅ 공휴일 및 휴일 관련 특징 추가
        if detect_results[target].get("has_quarterly_pattern", False):
            additional_features[f"{target}_is_rest_day_holiday"] = ((is_weekend == 1) | (is_holiday == 1)).astype(int)
            added_columns += [f"{target}_is_rest_day_holiday"]
        else:
            if detect_results[target].get("has_rest_day_effect", False):
                additional_features[f"{target}_is_weekend"] = is_weekend
                added_columns += [f"{target}_is_weekend"]
            if detect_results[target].get("has_holiday_effect", False):
                additional_features[f"{target}_is_holiday"] = is_holiday
                added_columns += [f"{target}_is_holiday"]
        # 공휴일 이동효과
        if detect_results[target].get("has_holiday_shift", False):
            additional_features[f"{target}_is_holiday_prev"] = is_holiday.shift(1, fill_value=0)
            additional_features[f"{target}_is_holiday_next"] = is_holiday.shift(-1, fill_value=0)
            added_columns += [f"{target}_is_holiday_prev", f"{target}_is_holiday_next"]
        # raw_data.drop(columns=[\'_is_weekend\'], inplace=True) # 삭제
        # raw_data.drop(columns=[\'_is_holiday\'], inplace=True) # 삭제
        # raw_data.drop(columns=[\'_day_of_week\'], inplace=True) # 삭제

    # 한 번에 추가
    new_features = pd.DataFrame(additional_features, index=raw_data.index)
    result_data = pd.concat([raw_data, new_features], axis=1)

    # ✅ 7. NaN만 포함된 컬럼 확인 후 제거
    nan_columns = result_data.columns[result_data.isna().all()].tolist()
    if nan_columns:
        ensembleForecaster_logger.info(f"🚨 NaN만 포함된 컬럼 제거: {nan_columns}")
        result_data = result_data.drop(columns=nan_columns)
        added_columns = [col for col in added_columns if col not in nan_columns]
        
    ensembleForecaster_logger.info(f"[{target}] 적용된 주기적 변환: {added_columns}")
    
    # defragmentation
    result_data = result_data.copy()
    
    return result_data, added_columns # raw_data 대신 result_data 반환

def generate_aggregation_features(raw_data, target_columns, detect_results):
    """
    집계 유형 추천 정보를 활용하여 집계 변수를 생성하는 함수.

    Parameters:
        raw_data (pd.DataFrame): 원본 데이터프레임 (datetime index 필요)
        target_columns (list): 집계할 대상 컬럼 리스트
        detect_results (dict): 탐지된 패턴 결과

    Returns:
        pd.DataFrame: 변환된 데이터프레임
        list: 추가된 특징 컬럼 리스트
    """

    added_columns = []
    df = raw_data.copy() # 원본 데이터프레임 복사하여 사용
    additional_agg_features = {} # 새로운 특성을 저장할 딕셔너리

    for target in target_columns:
        recommended_aggregations = detect_results[target].get("recommended_aggregations", []) # 키 존재 확인
        default_methods = ['min', 'max', 'std', 'sum']

        # ✅ 추천된 집계 유형 추가
        for method in recommended_aggregations:
            if method not in default_methods:
                default_methods.append(method)

        # ✅ 2. 원본 데이터 보간 (`resample('1h')` 전에 NaN 방지)
        # df[target] = df[target].ffill() # 이 부분은 resample 전에 원본 series에 대해 수행
        
        # ✅ 3. 1시간 단위 집계 수행
        valid_agg_methods = ['min', 'max', 'std', 'sum', 'mean', 'median', 'first', 'last', 'count', 'nunique', 'ohlc']
        
        resample_methods = {
            method: method for method in default_methods 
            if method != "diff_mean" and method in valid_agg_methods
        }

        try:
            # 대상 컬럼이 df에 있는지 확인
            if target not in df.columns:
                ensembleForecaster_logger.warning(f"[{target}] 컬럼이 데이터프레임에 없어 집계를 건너뜁니다.")
                continue

            target_series_for_resample = df[target].ffill() # 리샘플링 전 ffill

            if not resample_methods:
                ensembleForecaster_logger.warning(f"[{target}] 유효한 집계 메소드가 없어 집계를 건너뜁니다.")
                aggregated_df = pd.DataFrame(index=df.index) # 인덱스 맞춰주기
            else:
                aggregated_df = target_series_for_resample.resample('1h').agg(resample_methods).ffill()

            # ✅ 4. diff_mean 추가
            if "diff_mean" in recommended_aggregations and 'mean' in aggregated_df.columns:
                diff_mean_col_name = f"{target}_diff_mean"
                diff_series = aggregated_df['mean'].diff()
                interpolated_diff = diff_series.interpolate(method="linear")
                additional_agg_features[diff_mean_col_name] = interpolated_diff.fillna(0)
                added_columns.append(diff_mean_col_name)

            if 'max' in aggregated_df.columns and 'min' in aggregated_df.columns:
                # ✅ 5. max-min 차이값 추가
                range_col_name = f"{target}_range"
                range_series = aggregated_df["max"] - aggregated_df["min"]
                interpolated_range = range_series.interpolate(method="linear")
                additional_agg_features[range_col_name] = interpolated_range.fillna(0)
                added_columns.append(range_col_name)
            
            # Lag 기능 제거됨

        except Exception as e:
            ensembleForecaster_logger.error(f"[{target}] 집계 특성 생성 중 오류 발생: {e}", exc_info=True) # 상세 오류 로깅
            continue
    
    # 모든 루프가 끝난 후, additional_agg_features에 있는 모든 새 특성을 df에 한 번에 추가
    if additional_agg_features:
        new_features_df = pd.DataFrame(additional_agg_features, index=df.index)
        df = pd.concat([df, new_features_df], axis=1)

    # ✅ 7. NaN만 포함된 컬럼 확인 후 제거 (df 기준)
    if not df.empty: # df가 비어있지 않을 때만 실행
        nan_columns = df.columns[df.isna().all()].tolist()
        if nan_columns:
            ensembleForecaster_logger.info(f"🚨 NaN만 포함된 컬럼 제거: {nan_columns}")
            df = df.drop(columns=nan_columns)
            added_columns = [col for col in added_columns if col not in nan_columns]
    
    # ensembleForecaster_logger.info(f"적용된 집계 유형 추천: {added_columns}") # target 정보가 없어 루프 밖에서는 부적절
    
    return df, added_columns # 수정된 df와 추가된 컬럼명 리스트 반환

def detect_noise_level(raw_data, target_columns):
    """
    데이터 내 이상치(노이즈) 비율을 계산하는 함수.
    
    Parameters:
        raw_data (pd.DataFrame): 타겟 컬럼이 있는 데이터프레임
        target_columns (list): 이상치를 분석할 대상 컬럼 리스트
    
    Returns:
        float: 노이즈 비율 (0~1 사이 값)
    """
    total_outliers = pd.Series(False, index=raw_data.index)

    for col in target_columns:
        # IQR 기반 이상치 탐지
        Q1 = raw_data[col].quantile(0.25)
        Q3 = raw_data[col].quantile(0.75)
        IQR = Q3 - Q1
        iqr_outliers = (raw_data[col] < (Q1 - 1.5 * IQR)) | (raw_data[col] > (Q3 + 1.5 * IQR))

        # Z-score 기반 이상치 탐지
        z_scores = zscore(raw_data[col].dropna())
        z_outliers = np.abs(z_scores) > 3

        # 이동 평균 기반 이상치 탐지
        rolling_mean = raw_data[col].rolling(window=5, min_periods=1).mean()
        std_dev = rolling_mean.std()
        rolling_outliers = np.abs(raw_data[col] - rolling_mean) > std_dev

        # 이상치 비율 업데이트
        total_outliers |= iqr_outliers | z_outliers | rolling_outliers

    noise_ratio = total_outliers.sum() / len(raw_data)
    ensembleForecaster_logger.info(f"데이터 노이즈 비율: {noise_ratio:.2%}")

    return noise_ratio

def detect_best_scaler(data):
    """
    데이터 탐지를 통해 최적의 Scaler를 자동으로 선택하는 함수.

    Parameters:
        data (pd.Series or np.array): 스케일링할 대상 데이터 (1D)

    Returns:
        str: 추천 Scaler 이름
        bool: 로그 변환 필요 여부
    """
    data = np.array(data).reshape(-1, 1)  # 데이터 차원 조정
    log_transform_needed = False  # 기본적으로 로그 변환은 False

    # 1️⃣ 데이터의 최소값이 0 이하인지 확인 (MAPE 최적화 시 중요)
    if np.min(data) <= 0:
        log_transform_needed = True  # 0 이하 값이 있으면 로그 변환 필요

    # 2️⃣ 데이터의 평균과 표준편차 확인 → StandardScaler 적합성 판단
    mean_val, std_val = np.mean(data), np.std(data)
    if np.abs(mean_val) < 1 and 0.5 < std_val < 1.5:
        return "StandardScaler", log_transform_needed

    # 3️⃣ 데이터의 최소/최대 범위 확인 → MinMaxScaler 적합성 판단
    if data.min() >= 0 and data.max() < 100:
        return "MinMaxScaler", log_transform_needed

    # 4️⃣ 이상치(Outliers) 분석 → RobustScaler 필요 여부 판단
    q1, q3 = np.percentile(data, [25, 75])
    iqr = q3 - q1
    outlier_count = np.sum((data < (q1 - 1.5 * iqr)) | (data > (q3 + 1.5 * iqr)))
    if outlier_count > 0.05 * len(data):  # 이상치 비율이 5% 이상이면 RobustScaler 추천
        return "RobustScaler", log_transform_needed

    # 5️⃣ 데이터 분포 분석 → 정규성 판단 (Shapiro-Wilk Test, Skewness, Kurtosis)
    skewness = skew(data.flatten())  # 왜도 (Skewness)
    kurt = kurtosis(data.flatten())  # 첨도 (Kurtosis)

    if abs(skewness) > 1 or abs(kurt) > 3:
        # 비정규 분포이고 왜도가 크다면 QuantileTransformer or PowerTransformer 추천
        if np.min(data) > 0:  # 양수 데이터라면 PowerTransformer 추천
            return "PowerTransformer", log_transform_needed
        else:
            return "QuantileTransformer", log_transform_needed

    # 6️⃣ 양수 & 대칭적 데이터일 경우 → MaxAbsScaler 추천
    if np.min(data) >= 0 and np.max(data) <= 1:
        return "MaxAbsScaler", log_transform_needed

    # 기본값으로 StandardScaler 반환
    return "StandardScaler", log_transform_needed

def apply_scaling(df, target_columns, mode="per_feature", expanded_features=[]):
    """
    개별모드(Per-Feature Mode) & 단일모드(Global Mode)에서 Scaler를 자동으로 적용하는 함수.

    Parameters:
        df (pd.DataFrame): 원본 데이터프레임
        target_columns (list): 스케일링할 컬럼 리스트
        mode (str): "per_feature" (각 특징별 다른 Scaler 적용) 또는 "global" (전체 동일 Scaler 적용)

    Returns:
        pd.DataFrame: 스케일링된 데이터프레임
        dict: 적용된 Scaler 정보
    """
    if df.empty:
        ensembleForecaster_logger.warning("Input DataFrame to apply_scaling is empty. Returning empty structures.")
        # Ensure the return signature matches: scaled_df, scaler_dict, log_needed_dict, expanded_features
        return df.copy(), {}, {}, {}
    
    scaled_df = df.copy()
    scaler_dict = {}  # 각 컬럼에 적용된 Scaler 저장
    log_needed_dict = {}
    targets = {}
    if mode == "per_feature":
        # ✅ 개별모드: 각 target_column 별로 최적 Scaler 선택
        for target in target_columns:
            data_to_scale = df[target].dropna()
            if data_to_scale.empty:
                ensembleForecaster_logger.warning(f"[{target}] 스케일링할 데이터가 없어 StandardScaler를 기본값으로 사용합니다 (모든 값이 NaN).")
                best_scaler_name = "StandardScaler"
                log_needed = False
            else:
                best_scaler_name, log_needed = detect_best_scaler(data_to_scale)  # 최적 Scaler 탐지

            log_needed_dict[target] = log_needed # 로그 변환 필요 여부 저장

            # Scaler 객체 생성
            if best_scaler_name == "StandardScaler":
                scaler = StandardScaler()
            elif best_scaler_name == "MinMaxScaler":
                scaler = MinMaxScaler()
            elif best_scaler_name == "RobustScaler":
                scaler = RobustScaler()
            elif best_scaler_name == "QuantileTransformer":
                scaler = QuantileTransformer(output_distribution="uniform")
            elif best_scaler_name == "PowerTransformer":
                scaler = PowerTransformer()
            else:
                scaler = StandardScaler()  # 기본값
                
            scaler_dict[target] = scaler  # Scaler 저장
            scaled_df[target] = scaler.fit_transform(df[[target]])
            log_needed_dict[target] = log_needed  # log 필요여부 저장

    elif mode == "global":
        # ✅ 단일모드: 전체 데이터에 하나의 Scaler만 적용
        combined_data = np.concatenate([df[target].dropna().values.reshape(-1, 1) for target in target_columns], axis=0)
        best_scaler_name, log_needed = detect_best_scaler(combined_data)  # 전체 데이터 기준으로 최적 Scaler 탐지

        # Scaler 객체 생성
        if best_scaler_name == "StandardScaler":
            scaler = StandardScaler()
        elif best_scaler_name == "MinMaxScaler":
            scaler = MinMaxScaler()
        elif best_scaler_name == "RobustScaler":
            scaler = RobustScaler()
        elif best_scaler_name == "QuantileTransformer":
            scaler = QuantileTransformer(output_distribution="uniform")
        elif best_scaler_name == "PowerTransformer":
            scaler = PowerTransformer()
        else:
            scaler = StandardScaler()  # 기본값

        # ✅ 모든 target_columns에 동일한 Scaler 적용
        for target in target_columns:
            scaled_df[target] = scaler.fit_transform(df[[target]])
            scaler_dict[target] = scaler  # 모든 컬럼에 동일한 Scaler 저장
            log_needed_dict[target] = log_needed  # log 필요여부 저장
            
    for col in target_columns:
        scaled_df[col] = scaled_df[col].fillna(df[col])
    scaled_df = scaled_df.loc[:, ~scaled_df.columns.duplicated()]
    expanded_features = scaled_df.columns.tolist()
    
    return scaled_df, scaler_dict, log_needed_dict, expanded_features

# === 쾌적지수 함수 ===
def discomfort_index(temp, hum):
    return 0.81 * temp + 0.01 * hum * (0.99 * temp - 14.3) + 46.3

def make_sensor_column_map(raw_data_columns, settings):
    # 외부 공기 상태 (AWS)
    aws_columns = {}
    for k, filters in zip(['TEMP', 'RH', 'CO2'], [settings.TEMP_FILTER, settings.HUMIDITY_FILTER, settings.CO2_FILTER]):
        for f in filters:
            candidates = [col for col in raw_data_columns if col.startswith(settings.OUT_DOOR) and f in col]
            if candidates:
                aws_columns[k] = candidates[0]  # 첫 번째 매칭 컬럼만 사용 (여러개면 규칙 확장 필요)

    # 실내 공간별 센서 컬럼 매핑
    iaraw_columns = {}
    indoor_spaces = set([col.split('_')[0] for col in raw_data_columns if col.startswith(settings.IN_DOOR)])
    for space in indoor_spaces:
        iaraw_columns[space] = {}
        # TEMP
        temp_col = next((col for col in raw_data_columns if col.startswith(space) and any(f in col for f in settings.TEMP_FILTER)), None)
        if temp_col: iaraw_columns[space]['TEMP'] = temp_col
        # RH
        rh_col = next((col for col in raw_data_columns if col.startswith(space) and any(f in col for f in settings.HUMIDITY_FILTER)), None)
        if rh_col: iaraw_columns[space]['RH'] = rh_col
        # CO2
        co2_col = next((col for col in raw_data_columns if col.startswith(space) and any(f in col for f in settings.CO2_FILTER)), None)
        if co2_col: iaraw_columns[space]['CO2'] = co2_col

    return aws_columns, iaraw_columns

# === 쾌적지수 기반 피처 생성 함수 ===
def add_discomfort_features(raw_data, aws_columns, iaraw_columns):
    """
    Parameters:
        raw_data (pd.DataFrame): 전체 데이터프레임
        aws_columns (dict): 외기 상태 컬럼 매핑 (TEMP, RH, CO2)
        iaraw_columns (dict): 실내 공간별 컬럼 매핑 {'공간명': {'TEMP': col, 'RH': col, 'CO2': col}}

    Returns:
        raw_data (pd.DataFrame): 쾌적지수 및 피처 추가된 데이터
        added_columns (list): 새로 추가된 컬럼 리스트
    """
    added_columns = []

    # 외기 기준
    raw_data['outdoor_di'] = discomfort_index(raw_data[aws_columns['TEMP']], raw_data[aws_columns['RH']])
    added_columns.append('outdoor_di')

    for space, cols in iaraw_columns.items():
        temp_col, hum_col, co2_col = cols['TEMP'], cols['RH'], cols['CO2']

        di_col = f'{space}_di'
        raw_data[di_col] = discomfort_index(raw_data[temp_col], raw_data[hum_col])
        added_columns.append(di_col)

        level_col = f'{space}_level'
        raw_data[level_col] = pd.cut(raw_data[di_col],
            bins=[0, 68, 75, 100],
            labels=['comfort', 'uncomfortable', 'very_uncomfortable']
        )
        dummies = pd.get_dummies(raw_data[level_col], prefix=f'discomfort_{space}')
        raw_data = pd.concat([raw_data, dummies], axis=1)
        added_columns.extend(dummies.columns.tolist())

        # CO2 및 환기 관련
        co2_diff_col = f'{space}_co2_diff'
        raw_data[co2_diff_col] = raw_data[co2_col] - raw_data[aws_columns['CO2']]
        raw_data[f'{space}_need_vent'] = (raw_data[co2_diff_col] > 100).astype(int)
        raw_data[f'{space}_vent_burden'] = raw_data[f'{space}_need_vent'] * abs(
            raw_data[temp_col] - raw_data[aws_columns['TEMP']]
        )
        added_columns.extend([co2_diff_col, f'{space}_need_vent', f'{space}_vent_burden'])

    return raw_data, added_columns
