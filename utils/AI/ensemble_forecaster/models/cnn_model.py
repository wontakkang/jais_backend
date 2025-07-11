# cnn_model.py
"""
CNN (Convolutional Neural Network) 기반 시계열 예측 모델
- 1D Convolution 레이어 사용
- 하이퍼파라미터 튜닝 지원
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras

class CNNModel:
    
    model_type = 'DL' # 딥러닝 모델
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train, conv_filters=128, hidden_units=512, learning_rate=1e-3, loss_fn='mse'):
        if hasattr(self.config, 'purecnn_params'):
            params = self.config.purecnn_params
            conv_filters = params.get('conv_filters', conv_filters)
            hidden_units = params.get('hidden_units', hidden_units)
            learning_rate = params.get('learning_rate', learning_rate)
            loss_fn = params.get('loss', loss_fn)

        input_timesteps = X_train.shape[1]
        input_features = X_train.shape[2]

        if len(y_train.shape) == 2:
            y_train = y_train[:, None, :]
        output_seq_len = y_train.shape[1]
        output_features = y_train.shape[2]

        inputs = keras.layers.Input(shape=(input_timesteps, input_features))

        x = keras.layers.Conv1D(filters=conv_filters, kernel_size=5, activation='relu', padding='same')(inputs)
        x = keras.layers.Conv1D(filters=conv_filters * 2, kernel_size=5, activation='relu', padding='same')(x)
        x = keras.layers.GlobalAveragePooling1D()(x)

        x = keras.layers.Dense(hidden_units, activation='relu')(x)
        x = keras.layers.Dense(output_seq_len * output_features)(x)
        outputs = keras.layers.Reshape((output_seq_len, output_features))(x)

        model = keras.models.Model(inputs, outputs)

        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
            loss=loss_fn,
            metrics=['mae']
        )
        return model

    def build_with_hp(self, X_train, y_train, hp):
        conv_filters = hp.Choice('conv_filters', [32, 64, 128])
        hidden_units = hp.Choice('hidden_units', [32, 64, 128, 256, 512])
        learning_rate = hp.Choice('learning_rate', [1e-2, 1e-3, 1e-4])
        loss_fn = hp.Choice('loss', ['mse', 'huber'])

        return self.build(X_train, y_train,
                          conv_filters=conv_filters,
                          hidden_units=hidden_units,
                          learning_rate=learning_rate,
                          loss_fn=loss_fn)