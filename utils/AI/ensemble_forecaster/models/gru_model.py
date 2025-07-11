# GRU_model.py
"""
GRU (Gated Recurrent Unit) 기반 시계열 예측 모델
- 간소화된 RNN 셀 구조
- 하이퍼파라미터 튜닝 지원
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras

class GRUModel:
    
    model_type = 'DL' # 딥러닝 모델
    def __init__(self, config):
        """
        설정(config) 인스턴스를 받아 초기화
        """
        self.config = config

    def build(self, X_train, y_train, rnn_units=128, dropout_rate=0.1, learning_rate=1e-3):
        """
        GRU 모델 빌드 함수
        Parameters:
            - X_train: 입력 데이터
            - y_train: 출력 데이터
            - rnn_units: GRU 유닛 수
            - dropout_rate: Dropout 비율
            - learning_rate: 학습률
        Returns:
            - 모델 객체 (tf.keras.Model)
        """

        # ✅ 입력 차원 자동 추론
        input_timesteps = X_train.shape[1]
        input_features = X_train.shape[2]

        # ✅ 출력 차원 자동 보정
        if len(y_train.shape) == 2:
            y_train = np.expand_dims(y_train, axis=1)  # (batch, feature) → (batch, 1, feature)

        output_seq_len = y_train.shape[1]  # time_steps
        output_features = y_train.shape[2]  # feature_dim

        # 입력 레이어
        inputs = keras.layers.Input(shape=(input_timesteps, input_features))

        # 인코더 GRU
        x = keras.layers.GRU(rnn_units, return_sequences=False)(inputs)

        # 디코더 준비 (출력 시퀀스 길이만큼 복제)
        x = keras.layers.RepeatVector(output_seq_len)(x)

        # 디코더 GRU
        x = keras.layers.GRU(rnn_units, return_sequences=True)(x)

        # 드롭아웃 추가
        x = keras.layers.Dropout(dropout_rate)(x)

        # 출력 레이어
        outputs = keras.layers.TimeDistributed(keras.layers.Dense(output_features))(x)

        # 모델 구성
        model = keras.models.Model(inputs, outputs)

        # 컴파일
        model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate),
                      loss='mse',
                      metrics=['mae'])

        return model

    def build_with_hp(self, X_train, y_train, hp):
        """
        하이퍼파라미터 튜닝용 빌드 함수
        Parameters:
            - X_train: 입력 데이터
            - y_train: 출력 데이터
            - hp: keras_tuner HyperParameters 객체
        Returns:
            - 튜닝용 모델 객체
        """

        # 튜닝할 하이퍼파라미터 설정
        rnn_units = hp.Int('rnn_units', 32, 256, step=32)
        dropout_rate = hp.Float('dropout_rate', 0.0, 0.5, step=0.1)
        learning_rate = hp.Choice('learning_rate', [1e-2, 1e-3, 1e-4])

        # 위 하이퍼파라미터로 모델 빌드
        return self.build(X_train, y_train,
                          rnn_units=rnn_units,
                          dropout_rate=dropout_rate,
                          learning_rate=learning_rate)
