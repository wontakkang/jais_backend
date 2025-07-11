import pytz, io, json, os
from datetime import datetime, timedelta, timezone
from astral import LocationInfo
from astral.sun import sun
import re
import base64
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
import logging
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt
from astral import LocationInfo

# scoring funcs와 aggregate_metric 유틸 함수로 분리
def get_scoring_funcs():
    return {
        'R2 Score': r2_score,
        'Adjusted R2': lambda y_true, y_pred: adjusted_r2(
            y_true, y_pred,
            y_pred.shape[1] if np.ndim(y_pred) > 1 else 1
        ),
        'MSE': mean_squared_error,
        'MAE': mean_absolute_error,
        'MAPE': mean_absolute_percentage_error,
        'WMAPE': weighted_mean_absolute_percentage_error,
        'SMAPE': symmetric_mean_absolute_percentage_error,
        'CV(RMSE)': coefficient_of_variation_rmse,
        'NMBE': normalized_mean_bias_error,
        'RMSE': rmse,
        'VIF': lambda y_true, y_pred: np.mean(calculate_vif(y_pred)),
    }

def aggregate_metric(func, y_true_arr, y_pred_arr):
    return np.mean([func(y_true_arr[:, j], y_pred_arr[:, j]) for j in range(y_true_arr.shape[1])])

# AI Logger 설정
# # 🌞 7️⃣ 결과 출력
# import ace_tools_open as tools
# tools.display_dataframe_to_user(name="Processed Sun Position Data", dataframe=sun_data)

# NumPy 타입을 Python 내장 타입으로 변환하는 함수
def convert_numpy(obj):
    if isinstance(obj, np.bool_):
        return bool(obj)  # NumPy bool_ → Python bool 변환
    elif isinstance(obj, np.integer):
        return int(obj)  # NumPy int → Python int 변환
    elif isinstance(obj, np.floating):
        return float(obj)  # NumPy float → Python float 변환
    elif isinstance(obj, np.ndarray):
        return obj.tolist()  # NumPy 배열 → Python 리스트 변환
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def calculate_date_range_from_today(min_data_needed: int, lag: int, pred_date=None) -> tuple:
    """
    오늘 날짜(00시 기준)와 최소 필요 데이터 개수를 기반으로
    시작 날짜(start_date)와 종료 날짜(end_date)를 계산하는 함수
    
    :param min_data_needed: 최소 필요 데이터 개수
    :param lag: lag 차수
    :return: (start_date, end_date)
    """
    # 같은 요일 기준으로 데이터 일수를 계산하기 위해 오늘 날짜 계산
    if pred_date is not None:
        # pred_date가 주어진 경우 해당 날짜를 사용
        today = datetime.strptime(pred_date, "%Y%m%d")
        start_dt = today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7 + lag)
    else:
        start_dt = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7 + lag)
    # 시작 날짜 계산
    end_dt = start_dt + timedelta(days=min_data_needed)
    
    return start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d")


def filter_data(y_true, y_pred, threshold, percentile):
    """
    데이터 필터링 함수: 0에 가까운 값 및 하위 percentile 제외.

    Parameters:
        y_true (array-like): 실제 값
        y_pred (array-like): 예측 값
        threshold (float): 0에 가까운 값을 제외하는 절대 임계값
        percentile (float): 하위 특정 백분율을 제외하는 기준

    Returns:
        tuple: (필터링된 실제 값, 필터링된 예측 값)
    """
    # ✅ 0에 가까운 값 제외 (절대 임계값 방식)
    if threshold is not None:
        valid_indices = y_true > threshold
        y_true_filtered = y_true[valid_indices]
        y_pred_filtered = y_pred[valid_indices]
    else:
        y_true_filtered = y_true
        y_pred_filtered = y_pred

    # ✅ 하위 percentile 값 제외 (자동 임계값 방식)
    if percentile is not None and len(y_true_filtered) > 0:
        perc_threshold = np.percentile(y_true_filtered, percentile)
        valid_indices = y_true_filtered > perc_threshold
        y_true_filtered = y_true_filtered[valid_indices]
        y_pred_filtered = y_pred_filtered[valid_indices]

    return y_true_filtered, y_pred_filtered

def mean_absolute_percentage_error(y_true, y_pred, epsilon=1e-8, threshold=1e-3, percentile=None):
    """
    필터링된 MAPE (Mean Absolute Percentage Error)를 계산하는 함수.

    Parameters:
        y_true (array-like): 실제 값
        y_pred (array-like): 예측 값
        epsilon (float): 0 나누기 방지를 위한 작은 값 (기본값: 1e-8)
        threshold (float): 0에 가까운 값을 제외하는 절대 임계값 (기본값: 0.001, None이면 사용하지 않음)
        percentile (float): 하위 특정 백분율을 제외하는 기준 (예: 5 → 하위 5% 값 제외, 기본값: None)

    Returns:
        float: 필터링된 MAPE 값 (예외 발생 시 NaN 반환)
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)

    # 데이터 필터링
    y_true_filtered, y_pred_filtered = filter_data(y_true, y_pred, threshold, percentile)

    # 모든 값이 제외된 경우 NaN 반환
    if len(y_true_filtered) == 0:
        return np.nan

    # MAPE 계산
    return np.mean(np.abs((y_true_filtered - y_pred_filtered) / (y_true_filtered + epsilon))) * 100



def weighted_mean_absolute_percentage_error(y_true, y_pred, epsilon=1e-3, threshold=1e-3, percentile=None):
    """
    필터링된 WMAPE (Weighted Mean Absolute Percentage Error)를 계산하는 함수.

    Parameters:
        y_true (array-like): 실제 값
        y_pred (array-like): 예측 값
        epsilon (float): 0 나누기 방지를 위한 작은 값 (기본값: 1e-8)
        threshold (float): 0에 가까운 값을 제외하는 절대 임계값 (기본값: 0.001, None이면 사용하지 않음)
        percentile (float): 하위 특정 백분율을 제외하는 기준 (예: 5 → 하위 5% 값 제외, 기본값: None)

    Returns:
        float: 필터링된 WMAPE 값 (예외 발생 시 NaN 반환)
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)

    # 데이터 필터링
    y_true_filtered, y_pred_filtered = filter_data(y_true, y_pred, threshold, percentile)

    # 모든 값이 제외된 경우 NaN 반환
    if len(y_true_filtered) == 0:
        return np.nan

    # WMAPE 계산
    return np.sum(np.abs(y_true_filtered - y_pred_filtered)) / (np.sum(np.abs(y_true_filtered)) + epsilon) * 100

def symmetric_mean_absolute_percentage_error(y_true, y_pred, epsilon=1e-3, threshold=1e-3, percentile=None):
    """
    필터링된 SMAPE (Symmetric Mean Absolute Percentage Error)를 계산하는 함수.

    Parameters:
        y_true (array-like): 실제 값
        y_pred (array-like): 예측 값
        epsilon (float): 0 나누기 방지를 위한 작은 값 (기본값: 1e-8)
        threshold (float): 0에 가까운 값을 제외하는 절대 임계값 (기본값: 0.001, None이면 사용하지 않음)
        percentile (float): 하위 특정 백분율을 제외하는 기준 (예: 5 → 하위 5% 값 제외, 기본값: None)

    Returns:
        float: 필터링된 SMAPE 값 (예외 발생 시 NaN 반환)
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)

    # 데이터 필터링
    y_true_filtered, y_pred_filtered = filter_data(y_true, y_pred, threshold, percentile)

    # 모든 값이 제외된 경우 NaN 반환
    if len(y_true_filtered) == 0:
        return np.nan

    # SMAPE 계산
    return np.mean(2 * np.abs(y_true_filtered - y_pred_filtered) /
                   (np.abs(y_true_filtered) + np.abs(y_pred_filtered) + epsilon)) * 100


def coefficient_of_variation_rmse(y_true, y_pred, epsilon=1e-8):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mean_y_true = np.mean(y_true)
    return (np.sqrt(mean_squared_error(y_true, y_pred)) / (mean_y_true + epsilon)) * 100

def normalized_mean_bias_error(y_true, y_pred, epsilon=1e-8):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mean_y_true = np.mean(y_true)
    return (np.mean(y_pred - y_true) / (mean_y_true + epsilon)) * 100
def evaluate_performance(r2, adj_r2, mse, mae, mape, wmape, smape, cv_rmse, nmbe, rmse, vif):
    return [
        '매우 우수' if r2 > 0.9 else '좋음' if r2 > 0.75 else '평균' if r2 > 0.5 else '낮음',
        '매우 우수' if adj_r2 > 0.9 else '좋음' if adj_r2 > 0.75 else '평균' if adj_r2 > 0.5 else '낮음',
        '매우 우수' if mse < 10 else '좋음' if mse < 20 else '평균' if mse < 30 else '낮음',
        '매우 우수' if mae < 5 else '좋음' if mae < 10 else '평균' if mae < 15 else '낮음',
        '매우 우수' if mape < 5 else '좋음' if mape < 10 else '평균' if mape < 20 else '낮음',
        '매우 우수' if wmape < 5 else '좋음' if wmape < 10 else '평균' if wmape < 20 else '낮음',
        '매우 우수' if smape < 10 else '좋음' if smape < 15 else '평균' if smape < 25 else '낮음',
        '매우 우수' if cv_rmse < 5 else '좋음' if cv_rmse < 10 else '평균' if cv_rmse < 20 else '낮음',
        '매우 우수' if abs(nmbe) < 5 else '좋음' if abs(nmbe) < 10 else '평균' if abs(nmbe) < 20 else '낮음',
        '매우 우수' if rmse < 5 else '좋음' if rmse < 10 else '평균' if rmse < 20 else '낮음',
        '매우 우수' if vif < 5 else '좋음' if vif < 10 else '평균' if vif < 20 else '낮음'
    ]

def generate_final_conclusion(df_results):
    """
    성능 평가 결과를 기반으로 최종 결론 및 개선 방안을 제시하는 함수
    """
    min_r2 = df_results['R2 Score'].min()
    max_mse = df_results['MSE'].max()
    
    if min_r2 < 0.5 or max_mse > 30:
        conclusion = "일부 출력 차원의 모델 성능이 최적화되지 않았습니다. 개선이 필요합니다."
        recommendations = [
            "1. 특정 차원의 특성 엔지니어링을 개선하세요.",
            "2. 각 출력 차원의 하이퍼파라미터를 개별적으로 튜닝하세요.",
            "3. 복잡성을 줄여 과적합을 방지하세요.",
            "4. 데이터 분포를 확인하고 이상치를 해결하세요.",
        ]
    elif all(df_results['R2 Score'] > 0.75) and all(df_results['MSE'] < 20):
        conclusion = "모델 성능이 전반적으로 우수하며, 추가적인 개선 가능성이 있습니다."
        recommendations = [
            "1. 중요 특성을 검토하고 최적화를 고려하세요.",
            "2. 잔차 패턴을 평가하여 체계적인 오류를 확인하세요.",
            "3. 앙상블 기법을 활용하여 성능을 더욱 향상시키세요.",
        ]
    else:
        conclusion = "모델 성능이 양호하나 일부 출력에서 개선의 여지가 있습니다."
        recommendations = [
            "1. 높은 오류를 보이는 차원을 집중적으로 개선하세요.",
            "2. 교차 검증으로 일반화 성능을 확인하세요.",
            "3. 다른 알고리즘을 실험해보세요.",
        ]
    
    return conclusion, recommendations

def rmse(y, y_hat):
    return np.sqrt(np.mean((y - y_hat) ** 2))

def nmbe(y, y_hat):
    bias = np.sum(y - y_hat)
    return (bias / (len(y) * np.mean(y))) * 100  # %로 반환

def adjusted_r2(y_true, y_pred, num_features):
    n = len(y_true)
    r2 = r2_score(y_true, y_pred)
    return 1 - (1 - r2) * (n - 1) / (n - num_features - 1)

def calculate_vif(X):
    # 배열 차원 검사: 1D 입력은 2D 형태로 변환
    X = np.array(X)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    vif_data = []
    for i in range(X.shape[1]):
        X_i = X[:, i]
        X_others = np.delete(X, i, axis=1)
        X_others = np.hstack([np.ones((X_others.shape[0], 1)), X_others])
        beta = np.linalg.inv(X_others.T @ X_others) @ X_others.T @ X_i
        X_i_pred = X_others @ beta
        ss_res = np.sum((X_i - X_i_pred) ** 2)
        ss_tot = np.sum((X_i - np.mean(X_i)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)
        vif = 1 / (1 - r_squared)
        vif_data.append(vif)
    return vif_data

def evaluate_models(y_true, y_preds_base, y_pred_ensemble, column_names=None):
    """
    베이스 모델들과 앙상블 모델의 성능을 평가하는 함수 (다차원 데이터 지원)
    """
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

    scoring_funcs = get_scoring_funcs()

    results = []
    evaluations = []

    # 베이스 모델 성능 평가
    for i, y_pred in enumerate(y_preds_base):
        vals = [aggregate_metric(func, y_true, y_pred) for func in scoring_funcs.values()]
        results.append([f'Base Model {i+1}'] + vals)
        evaluations.append(evaluate_performance(*vals))

    # 앙상블 모델 성능 평가 추가
    vals = [aggregate_metric(func, y_true, y_pred_ensemble) for func in scoring_funcs.values()]
    results.append([f'Ensemble Model'] + vals)
    evaluations.append(evaluate_performance(*vals))

    # 결과 데이터프레임 생성
    df_results = pd.DataFrame(results, columns=['Model'] + metrics)
    df_evaluations = pd.DataFrame(evaluations, columns=evaluation_metrics)
    df_results = pd.concat([df_results, df_evaluations], axis=1)
    
    conclusion, recommendations = generate_final_conclusion(df_results)
    
    return df_results, conclusion, recommendations


def split_time_series(X_df, y_df, datetime_col="datetime", test_size=0.2):
    """
    DatetimeIndex를 가진 두 개의 데이터프레임 (X, y)을 날짜(day) 단위로 그룹화하여 
    train-test split을 수행한다. (shuffle=False)
    
    Parameters:
    - X_df (pd.DataFrame): 독립 변수 (피처 데이터, DatetimeIndex)
    - y_df (pd.DataFrame): 종속 변수 (타겟 데이터, DatetimeIndex)
    - test_size (float): 테스트 데이터 비율 (기본값: 0.2)
    
    Returns:
    - X_train, X_test, y_train, y_test
    """

    # 날짜 기준으로 그룹화 (DatetimeIndex의 날짜 추출)
    X_df["date"] = X_df.index.date
    y_df["date"] = y_df.index.date

    # 고유한 날짜 리스트 추출
    unique_dates = X_df["date"].unique()

    # Train-Test 날짜 기준으로 분할
    train_size = int(len(unique_dates) * (1 - test_size))
    train_dates = unique_dates[:train_size]
    test_dates = unique_dates[train_size:]

    # 날짜 기반 데이터 분할
    X_train = X_df[X_df["date"].isin(train_dates)].drop(columns=["date"])
    X_test = X_df[X_df["date"].isin(test_dates)].drop(columns=["date"])

    y_train = y_df[y_df["date"].isin(train_dates)].drop(columns=["date"])
    y_test = y_df[y_df["date"].isin(test_dates)].drop(columns=["date"])

    return X_train, X_test, y_train, y_test


def plot_results(y_true, y_pred, model_name, metric_names=None):
    # 길이 및 차원 맞추기
    if isinstance(y_true, pd.DataFrame): y_true = y_true.to_numpy()
    if isinstance(y_pred, pd.DataFrame): y_pred = y_pred.to_numpy()
    # ✅ 길이 맞추기 (차원 변경 없이)
    min_len = min(len(y_true), len(y_pred))
    y_true, y_pred = y_true[:min_len-1], y_pred[:min_len-1]
    if y_true.ndim == 1: y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1: y_pred = y_pred.reshape(-1, 1)
    # 지표 계산
    default_names = ['R2 Score', 'MAE', 'RMSE', 'NMBE']
    names = metric_names or default_names
    funcs = get_scoring_funcs()
    metrics_per_dim = {name: [funcs[name](y_true[:, i], y_pred[:, i]) for i in range(y_true.shape[1])] for name in names}
    # 시각화: 출력 차원별
    n_outputs = y_true.shape[1]
    fig, axes = plt.subplots(1, n_outputs, figsize=(6*n_outputs, 6), squeeze=False)
    axes = axes.flatten()
    for i, ax in enumerate(axes):
        ax.plot(y_true[:, i], label='y_true', color='red', alpha=0.7)
        ax.plot(y_pred[:, i], label='y_pred', color='green', linestyle='--', alpha=0.7)
        ax.set_title(f'Output {i+1} ({model_name})')
        ax.set_xlabel('Samples')
        ax.set_ylabel('Value')
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)
        # 차원별 지표 overlay
        metric_text = '\n'.join([f"{name}: {metrics_per_dim[name][i]:.2f}" for name in names])
        ax.text(0.02, 0.98, metric_text, transform=ax.transAxes, va='top', fontsize=10, color='black')
    fig.tight_layout()
    # 이미지 저장
    image_dir = "/tmp/"
    os.makedirs(image_dir, exist_ok=True)
    image_path = os.path.join(image_dir, "plot.png")
    plt.savefig(image_path, format="png")
    plt.close(fig)
    return image_path

def plot_results_live(y_true, y_pred, model_name, metric_names=None):
    """
    실제 값과 예측 값을 비교하는 그래프를 그리는 함수. 다차원 출력 및 사용자 정의 지표 지원.
    """
    # 길이 및 차원 맞추기
    if isinstance(y_true, pd.DataFrame): y_true = y_true.to_numpy()
    if isinstance(y_pred, pd.DataFrame): y_pred = y_pred.to_numpy()
    # ✅ 길이 맞추기 (차원 변경 없이)
    min_len = min(len(y_true), len(y_pred))
    y_true, y_pred = y_true[:min_len-1], y_pred[:min_len-1]
    if y_true.ndim == 1: y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1: y_pred = y_pred.reshape(-1, 1)
    # 지표 계산
    default_names = ['R2 Score', 'MAE', 'RMSE', 'NMBE']
    names = metric_names or default_names
    funcs = get_scoring_funcs()
    metrics_per_dim = {name: [funcs[name](y_true[:, i], y_pred[:, i]) for i in range(y_true.shape[1])] for name in names}
    # 시각화: 출력 차원별 동적 생성
    n_outputs = y_true.shape[1]
    fig, axes = plt.subplots(1, n_outputs, figsize=(6*n_outputs, 6), squeeze=False)
    axes = axes.flatten()
    for i, ax in enumerate(axes):
        ax.plot(y_true[:, i], label='y_true', color='red', alpha=0.7)
        ax.plot(y_pred[:, i], label='y_pred', color='green', linestyle='--', alpha=0.7)
        ax.set_title(f'Output {i+1} ({model_name})')
        ax.set_xlabel('Samples')
        ax.set_ylabel('Value')
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)
        # 차원별 지표 표시
        metric_text = '\n'.join([f"{name}: {metrics_per_dim[name][i]:.2f}" for name in names])
        ax.text(0.02, 0.98, metric_text, transform=ax.transAxes, va='top', fontsize=10, color='black')
    fig.tight_layout()
    # 이미지 저장 및 반환
    image_dir = '/tmp/'
    os.makedirs(image_dir, exist_ok=True)
    image_path = os.path.join(image_dir, 'plot_live.png')
    plt.savefig(image_path, format='png')
    plt.close(fig)
    return image_path
    
def plot_results_html_content(y_true, y_pred, model_name, metric_names=None):
    """
    실제 값과 예측 값을 비교하는 그래프를 그리는 함수 (R², MAE, RMSE 포함).
    
    Parameters:
        y_true (array-like): 실제 값 (일사량, 전력 소비량)
        y_pred (array-like): 예측 값 (일사량, 전력 소비량)
        model_name (str): 모델 이름

    Returns:
        str: Base64로 인코딩된 HTML 그래프 이미지
    """
    # ✅ 길이 맞추기 (차원 변경 없이)
    min_len = min(len(y_true), len(y_pred))
    y_true = y_true[:min_len-1]
    y_pred = y_pred[:min_len-1]

    # ✅ 1️⃣ 데이터 변환 (DataFrame → NumPy 변환)
    if isinstance(y_true, pd.DataFrame):
        y_true = y_true.to_numpy()
    if isinstance(y_pred, pd.DataFrame):
        y_pred = y_pred.to_numpy()

    # ✅ 2️⃣ 1차원 배열을 2차원으로 변환
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)

    # ✅ 3️⃣ 평가 지표 계산 및 평균화 (MAE, RMSE, R², NMBE)
    default_names = ['R2 Score', 'MAE', 'RMSE', 'NMBE']
    names = metric_names or default_names
    funcs = get_scoring_funcs()
    n_outputs = y_true.shape[1]
    metrics_per_dim = {name: [funcs[name](y_true[:, i], y_pred[:, i]) for i in range(n_outputs)] for name in names}
    mae_sunlight, mae_power = metrics_per_dim['MAE']
    rmse_sunlight, rmse_power = metrics_per_dim['RMSE']
    r2_sunlight, r2_power = metrics_per_dim['R2 Score']
    nmbe_sunlight, nmbe_power = metrics_per_dim['NMBE']
    agg_metrics = {name: aggregate_metric(funcs[name], y_true, y_pred) for name in names}

    # ✅ 4️⃣ 시각화 (출력 차원별 동적 서브플롯 및 지표 표시)
    fig, axes = plt.subplots(1, n_outputs, figsize=(6*n_outputs, 6), squeeze=False)
    axes = axes.flatten()
    for i, ax in enumerate(axes):
        ax.plot(y_true[:, i], label='y_true', color='red', alpha=0.7)
        ax.plot(y_pred[:, i], label='y_pred', color='green', linestyle='--', alpha=0.7)
        ax.set_title(f'Output {i+1} ({model_name})')
        ax.set_xlabel('Samples')
        ax.set_ylabel('Value')
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.6)
        # 차원별 지표 overlay
        metric_text = '\n'.join([f"{name}: {metrics_per_dim[name][i]:.2f}" for name in names])
        ax.text(0.02, 0.98, metric_text, transform=ax.transAxes, va='top', fontsize=10, color='black')
    fig.tight_layout()
    # 하단 중앙 전체 평균 지표 표시
    agg_text = ', '.join([f"Avg {name}: {agg_metrics[name]:.2f}" for name in names])
    fig.text(0.5, 0.01, agg_text, ha='center', fontsize=10)

    # ✅ 5️⃣ 그래프를 이미지로 변환
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format="png")
    plt.close(fig)  # 플롯을 닫아 메모리 절약
    img_buf.seek(0)
    
    # ✅ 6️⃣ 이미지 데이터를 Base64로 인코딩
    img_base64 = base64.b64encode(img_buf.getvalue()).decode("utf-8")

    # ✅ 7️⃣ HTML 코드 생성
    html_content = f"""
    <html>
    <head>
        <title>Model Performance</title>
    </head>
    <body>
        <h2>Model: {model_name}</h2>
        <img src="data:image/png;base64,{img_base64}" alt="Generated Plot">
    </body>
    </html>
    """

    return html_content


def plot_html_content(y_true, y_pred, model_name):
    """
    실제 값과 예측 값을 비교하는 그래프를 그리는 함수 (R², MAE, RMSE 포함).
    
    Parameters:
        y_true (array-like): 실제 값 (일사량, 전력 소비량)
        y_pred (array-like): 예측 값 (일사량, 전력 소비량)
        model_name (str): 모델 이름

    Returns:
        str: Base64로 인코딩된 HTML 그래프 이미지
    """
    # ✅ 1️⃣ 데이터 변환 (DataFrame → NumPy 변환)
    if isinstance(y_true, pd.DataFrame):
        y_true = y_true.to_numpy()
    if isinstance(y_pred, pd.DataFrame):
        y_pred = y_pred.to_numpy()

    # ✅ 2️⃣ 1차원 배열을 2차원으로 변환
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)


    # ✅ 3️⃣ 평가 지표 계산 및 평균화 (동적)
    names = ['MAE','RMSE','R2 Score','NMBE']
    funcs = get_scoring_funcs()
    n_outputs = y_true.shape[1]
    metrics_per_dim = {name: [funcs[name](y_true[:, i], y_pred[:, i]) for i in range(n_outputs)] for name in names}
    agg_metrics = {name: aggregate_metric(funcs[name], y_true, y_pred) for name in names}
    # ✅ 4️⃣ 시각화 (출력 차원별 동적 서브플롯 및 지표 표시)
    fig, axes = plt.subplots(1, n_outputs, figsize=(6*n_outputs, 6), squeeze=False)
    axes = axes.flatten()
    for i, ax in enumerate(axes):
        ax.plot(y_true[:, i], label='y_true', color='red', alpha=0.7)
        ax.plot(y_pred[:, i], label='y_pred', color='green', linestyle='--', alpha=0.7)
        ax.set_title(f'Output {i+1} ({model_name})')
        ax.set_xlabel('Samples')
        ax.set_ylabel('Value')
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.6)
        metric_text = '\n'.join([f"{name}: {metrics_per_dim[name][i]:.2f}" for name in names])
        ax.text(0.02, 0.98, metric_text, transform=ax.transAxes, va='top', fontsize=10, color='black')
    # ✅ `fig.tight_layout()` 적용
    fig.tight_layout()
    # 하단 중앙 전체 평균 지표 표시
    agg_text = ', '.join([f"Avg {name}: {agg_metrics[name]:.2f}" for name in names])
    fig.text(0.5, 0.01, agg_text, ha='center', fontsize=10)

    # ✅ 5️⃣ 그래프를 이미지로 변환
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format="png")
    plt.close(fig)  # 플롯을 닫아 메모리 절약
    img_buf.seek(0)
    
    # ✅ 6️⃣ 이미지 데이터를 Base64로 인코딩
    img_base64 = base64.b64encode(img_buf.getvalue()).decode("utf-8")

    # ✅ 7️⃣ HTML 코드 생성
    html_content = f"""
    <html>
    <head>
        <title>Model Performance</title>
    </head>
    <body>
        <h2>Model: {model_name}</h2>
        <img src="data:image/png;base64,{img_base64}" alt="Generated Plot">
    </body>
    </html>
    """

    return html_content


def get_sunrise_sunset(lat, lon, date=None, tz="Asia/Seoul"):
    """
    주어진 위도(lat), 경도(lon)에서 일출 및 일몰 시간을 계산하는 함수 (한국 시간 변환).
    
    :param lat: 위도
    :param lon: 경도
    :param date: 특정 날짜 (기본값: 오늘)
    :param tz: 시간대 (기본값: 한국 시간대 "Asia/Seoul")
    :return: 일출 및 일몰 시간 (datetime 객체, KST 기준)
    """
    if date is None:
        date = datetime.today()

    location = LocationInfo(latitude=lat, longitude=lon)
    s = sun(location.observer, date=date)

    local_tz = pytz.timezone(tz)  # ✅ pytz 사용으로 수정
    sunrise = s["sunrise"].replace(tzinfo=pytz.utc).astimezone(local_tz)
    sunset = s["sunset"].replace(tzinfo=pytz.utc).astimezone(local_tz)

    return sunrise, sunset


def convert_numpy_types(obj):
    """
    넘파이 타입들을 JSON 직렬화 가능한 기본 타입으로 변환
    """
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(v) for v in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    else:
        return obj


def get_latest_trial_path(base_dir, trial_num=None):
    """
    지정된 또는 최신 trial_숫자 경로 반환
    """
    print(f"base_dir: {base_dir}")
    os.makedirs(base_dir, exist_ok=True)

    if trial_num is not None:
        trial_path = os.path.join(base_dir, f"trial_{trial_num}")
        if not os.path.exists(trial_path):
            raise FileNotFoundError(f"{trial_path} 디렉토리가 존재하지 않습니다.")
        return trial_path

    existing_trials = [
        (int(m.group(1)), os.path.join(base_dir, d)) for d in os.listdir(base_dir)
        if (m := re.match(r"trial_(\d+)", d)) and os.path.isdir(os.path.join(base_dir, d))
    ]

    if not existing_trials:
        raise FileNotFoundError("저장된 trial_폴더가 없습니다.")
    return max(existing_trials, key=lambda x: x[0])[1]


def get_next_trial_path(base_dir, trial_num=None):
    """
    지정된 또는 자동으로 다음 trial_숫자 디렉토리 생성
    """
    os.makedirs(base_dir, exist_ok=True)

    if trial_num is not None:
        trial_path = os.path.join(base_dir, f"trial_{trial_num}")
    else:
        existing_trials = [
            int(m.group(1)) for d in os.listdir(base_dir)
            if (m := re.match(r"trial_(\d+)", d)) and os.path.isdir(os.path.join(base_dir, d))
        ]
        next_num = max(existing_trials, default=0) + 1
        trial_path = os.path.join(base_dir, f"trial_{next_num}")

    os.makedirs(trial_path, exist_ok=True)
    return trial_path


def get_sunrise_sunset(lat, lon, date=None, tz="Asia/Seoul"):
    """
    주어진 위도(lat), 경도(lon)에서 일출 및 일몰 시간을 계산하는 함수 (한국 시간 변환).
    
    :param lat: 위도
    :param lon: 경도
    :param date: 특정 날짜 (기본값: 오늘)
    :param tz: 시간대 (기본값: 한국 시간대 "Asia/Seoul")
    :return: 일출 및 일몰 시간 (datetime 객체, KST 기준)
    """
    if date is None:
        date = datetime.today()

    location = LocationInfo(latitude=lat, longitude=lon)
    s = sun(location.observer, date=date)

    local_tz = pytz.timezone(tz)  # ✅ pytz 사용으로 수정
    sunrise = s["sunrise"].replace(tzinfo=pytz.utc).astimezone(local_tz)
    sunset = s["sunset"].replace(tzinfo=pytz.utc).astimezone(local_tz)

    return sunrise, sunset

def save_ml_tuning_report(model_name, cleaned_params, metric_score=None, report_dir="./tuning_reports"):
    # 1. 모델명 기반 기본 폴더
    base_dir = os.path.join(report_dir, f"{model_name.lower()}_tuning")
    os.makedirs(base_dir, exist_ok=True)  # ✅ 없으면 생성

    # 2. trial_숫자 폴더 목록 읽기
    existing_trials = [d for d in os.listdir(base_dir) if d.startswith("trial_")]
    existing_trials = [int(d.split('_')[1]) for d in existing_trials if d.split('_')[1].isdigit()]
    next_trial_num = max(existing_trials) + 1 if existing_trials else 0

    # 3. 새 trial_x 폴더 생성
    trial_dir = os.path.join(base_dir, f"trial_{next_trial_num}")
    os.makedirs(trial_dir, exist_ok=True)  # ✅ 없으면 생성
    # 4. trial.json 저장
    report = {
        "best_params": cleaned_params,
        'metric_score': metric_score if metric_score is not None else {},
    }
    report_path = os.path.join(trial_dir, "trial.json")  # ✅ 파일명 고정

    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)

    print(f"✅ 튜닝 리포트 저장 완료: {report_path}")

def plot_residual_patterns_html_content(y_true, y_pred, model_name, column_names=None):
    """
    잔차 패턴을 시각화하여 HTML 컨텐츠로 반환하는 함수.

    Parameters:
        y_true (array-like): 실제 값.
        y_pred (array-like): 예측 값.
        model_name (str): 모델 이름.
        column_names (list of str, optional): 다중 출력 시 각 출력의 이름.

    Returns:
        str: Base64로 인코딩된 HTML 그래프 이미지.
    """
    # 데이터 변환 (DataFrame → NumPy 변환)
    if isinstance(y_true, pd.DataFrame):
        y_true = y_true.to_numpy()
    if isinstance(y_pred, pd.DataFrame):
        y_pred = y_pred.to_numpy()

    # 1차원 배열을 2차원으로 변환
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)

    if y_true.shape[1] != y_pred.shape[1]:
        raise ValueError("y_true와 y_pred의 출력 특성 수가 일치해야 합니다.")

    num_outputs = y_true.shape[1]
    
    if column_names is None:
        column_names = [f"Output {i+1}" for i in range(num_outputs)]
    elif len(column_names) != num_outputs:
        raise ValueError("column_names의 길이와 출력 특성 수가 일치해야 합니다.")

    residuals = y_true - y_pred

    fig, axes = plt.subplots(num_outputs, 2, figsize=(15, 5 * num_outputs), squeeze=False)
    
    for i in range(num_outputs):
        # 잔차 대 예측값 플롯
        axes[i, 0].scatter(y_pred[:, i], residuals[:, i], alpha=0.5)
        axes[i, 0].axhline(0, color='red', linestyle='--')
        axes[i, 0].set_xlabel(f"Predicted Values ({column_names[i]})")
        axes[i, 0].set_ylabel(f"Residuals ({column_names[i]})")
        axes[i, 0].set_title(f"Residuals vs. Predicted ({column_names[i]})")
        axes[i, 0].grid(True, linestyle="--", alpha=0.6)

        # 잔차 히스토그램
        axes[i, 1].hist(residuals[:, i], bins=30, alpha=0.7, color='blue')
        axes[i, 1].axvline(residuals[:, i].mean(), color='red', linestyle='--', label=f"Mean: {residuals[:, i].mean():.2f}")
        axes[i, 1].set_xlabel(f"Residuals ({column_names[i]})")
        axes[i, 1].set_ylabel("Frequency")
        axes[i, 1].set_title(f"Histogram of Residuals ({column_names[i]})")
        axes[i, 1].legend()
        axes[i, 1].grid(True, linestyle="--", alpha=0.6)

    fig.suptitle(f"Residual Analysis for {model_name}", fontsize=16, y=1.02 if num_outputs > 1 else 1.05)
    fig.tight_layout(rect=[0, 0, 1, 0.98 if num_outputs > 1 else 0.95]) # Adjust layout to make space for suptitle

    # 그래프를 이미지로 변환
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format="png")
    plt.close(fig)  # 플롯을 닫아 메모리 절약
    img_buf.seek(0)
    
    # 이미지 데이터를 Base64로 인코딩
    img_base64 = base64.b64encode(img_buf.getvalue()).decode("utf-8")

    # HTML 코드 생성
    html_content = f"""
    <html>
    <head>
        <title>Residual Analysis: {model_name}</title>
    </head>
    <body>
        <h2>Residual Analysis for Model: {model_name}</h2>
        <img src="data:image/png;base64,{img_base64}" alt="Residual Plots">
    </body>
    </html>
    """
    return html_content

def test_rmse_simple():
    y = np.array([0, 1, 2, 3])
    y_hat = np.array([0, 1, 1, 4])
    expected = np.sqrt(mean_squared_error(y, y_hat))
    return bool(np.isclose(rmse(y, y_hat), expected))

def test_nmbe_zero_bias():
    y = np.array([10, 10, 10])
    y_hat = np.array([10, 10, 10])
    return bool(np.isclose(nmbe(y, y_hat), 0.0))

def test_vif_independent():
    # 독립 변수 두 개
    x1 = np.random.rand(100)
    x2 = np.random.rand(100)
    X = np.column_stack([x1, x2])
    vif = calculate_vif(X)
    # 서로 독립이면 VIF ≈ 1
    return all(0.9 < v < 1.1 for v in vif)

# 🔍 추가 평가지표 검증 테스트
def test_r2_perfect():
    y = np.array([1, 2, 3, 4])
    y_hat = y.copy()
    func = get_scoring_funcs()['R2 Score']
    return bool(np.isclose(func(y, y_hat), 1.0))

def test_adjusted_r2_perfect():
    y = np.array([1, 2, 3, 4])
    y_hat = y.copy()
    func = get_scoring_funcs()['Adjusted R2']
    # num_features 모수로 인한 차원은 임의 1 설정
    return bool(np.isclose(func(y, y_hat), 1.0))

def test_mse_basic():
    y = np.array([0, 1, 2])
    y_hat = np.array([1, 1, 2])
    func = get_scoring_funcs()['MSE']
    expected = mean_squared_error(y, y_hat)
    return bool(np.isclose(func(y, y_hat), expected))

def test_mae_basic():
    y = np.array([0, 1, 2])
    y_hat = np.array([1, 1, 2])
    func = get_scoring_funcs()['MAE']
    expected = mean_absolute_error(y, y_hat)
    return bool(np.isclose(func(y, y_hat), expected))

def test_mape_basic():
    y = np.array([10, 20])
    y_hat = np.array([12, 18])
    func = get_scoring_funcs()['MAPE']
    # (|2/10| + |2/20|)/2*100 = 15
    return bool(np.isclose(func(y, y_hat), 15.0))

def test_wmape_basic():
    y = np.array([10, 20])
    y_hat = np.array([12, 18])
    func = get_scoring_funcs()['WMAPE']
    # WMAPE 계산 시 내부 epsilon(1e-3) 포함
    expected = (np.sum(np.abs(y - y_hat)) / (np.sum(np.abs(y)) + 1e-3)) * 100
    return bool(np.isclose(func(y, y_hat), expected))

def test_smape_basic():
    y = np.array([10, 20])
    y_hat = np.array([12, 18])
    func = get_scoring_funcs()['SMAPE']
    # SMAPE 계산 시 내부 epsilon(1e-3) 포함
    diffs = 2 * np.abs(y - y_hat)
    denoms = np.abs(y) + np.abs(y_hat) + 1e-3
    expected = np.mean(diffs / denoms) * 100
    return bool(np.isclose(func(y, y_hat), expected))

def test_cv_rmse_basic():
    y = np.array([1, 2, 3])
    y_hat = np.array([1, 2, 2])
    func = get_scoring_funcs()['CV(RMSE)']
    # rmse=√(1/3)=0.57735, mean_y=2 → (0.57735/2)*100 ≈28.8675
    expected = (np.sqrt(mean_squared_error(y, y_hat)) / np.mean(y)) * 100
    return bool(np.isclose(func(y, y_hat), expected))

