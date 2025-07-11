import numpy as np
import keras

class LSTMModel:
    
    model_type = 'DL' # 딥러닝 모델
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train, lstm_units=64, num_layers=1, hidden_units=512, dropout_rate=0.1, learning_rate=1e-3, loss_fn='mse'):
        if hasattr(self.config, 'lstm_params'):
            lstm_params = self.config.lstm_params
            lstm_units = lstm_params.get('lstm_units', lstm_units)
            num_layers = lstm_params.get('num_layers', num_layers)
            hidden_units = lstm_params.get('hidden_units', hidden_units)
            dropout_rate = lstm_params.get('dropout_rate', dropout_rate)
            learning_rate = lstm_params.get('learning_rate', learning_rate)
            loss_fn = lstm_params.get('loss', loss_fn)
        input_timesteps = X_train.shape[1]
        input_features = X_train.shape[2]

        if len(y_train.shape) == 2:
            y_train = y_train[:, None, :]
        output_seq_len = y_train.shape[1]
        output_features = y_train.shape[2]

        inputs = keras.layers.Input(shape=(input_timesteps, input_features))
        x = inputs

        # ✅ 여러 LSTM 층을 쌓기
        for i in range(num_layers):
            return_seq = i < num_layers - 1  # 마지막 층은 False
            x = keras.layers.LSTM(units=lstm_units, return_sequences=return_seq)(x)
        x = keras.layers.LayerNormalization()(x)
        x = keras.layers.BatchNormalization()(x)
        x = keras.layers.Dropout(dropout_rate)(x)
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
        hp_grid = self.config.hyperparameter_grids.get('LSTMModel', {})
        lstm_units = hp.Choice('lstm_units', hp_grid.get('lstm_units', [32, 64, 128, 256]))
        num_layers = hp.Choice('num_layers', hp_grid.get('num_layers', [1, 2, 3]))
        hidden_units = hp.Choice('hidden_units', hp_grid.get('hidden_units', [32, 64, 128, 256, 512]))
        dropout_rate = hp.Choice('dropout_rate', hp_grid.get('dropout_rate', [0.0, 0.1, 0.3, 0.5]))
        learning_rate = hp.Choice('learning_rate', hp_grid.get('learning_rate', [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2]))
        loss_fn = hp.Choice('loss', hp_grid.get('loss', ['mse', 'huber']))

        return self.build(X_train, y_train,
                          lstm_units=lstm_units,
                          num_layers=num_layers,
                          hidden_units=hidden_units,
                          dropout_rate=dropout_rate,
                          learning_rate=learning_rate,
                          loss_fn=loss_fn)
