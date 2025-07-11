import numpy as np
import keras

class TFTModel:
    model_type = 'DL' # 딥러닝 모델
    
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train, num_heads=4, hidden_size=128, hidden_units=512, dropout_rate=0.1, learning_rate=1e-3, loss_fn='mse'):
        if hasattr(self.config, 'tft_params'):
            params = self.config.tft_params
            num_heads = params.get('num_heads', num_heads)
            hidden_size = params.get('hidden_size', hidden_size)
            hidden_units = params.get('hidden_units', hidden_units)
            dropout_rate = params.get('dropout_rate', dropout_rate)
            learning_rate = params.get('learning_rate', learning_rate)
            loss_fn = params.get('loss', loss_fn)

        input_timesteps = X_train.shape[1]
        input_features = X_train.shape[2]

        if len(y_train.shape) == 2:
            y_train = y_train[:, None, :]
        output_seq_len = y_train.shape[1]
        output_features = y_train.shape[2]

        inputs = keras.layers.Input(shape=(input_timesteps, input_features))

        x = keras.layers.MultiHeadAttention(num_heads=num_heads, key_dim=hidden_size)(inputs, inputs)
        x = keras.layers.Add()([x, inputs])
        x = keras.layers.GlobalAveragePooling1D()(x)
        x = keras.layers.LayerNormalization()(x)
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
        hp_grid = self.config.hyperparameter_grids.get('TFTModel', {})

        num_heads = hp.Choice('num_heads', hp_grid.get('num_heads', [2, 4, 6, 8]))
        hidden_size = hp.Choice('hidden_size', hp_grid.get('hidden_size', [32, 64, 128]))
        hidden_units = hp.Choice('hidden_units', hp_grid.get('hidden_units', [32, 64, 128, 256, 512]))
        dropout_rate = hp.Choice('dropout_rate', hp_grid.get('dropout_rate', [0.1, 0.2, 0.3]))
        learning_rate = hp.Choice('learning_rate', hp_grid.get('learning_rate', [1e-2, 1e-3, 1e-4]))
        loss_fn = hp.Choice('loss', hp_grid.get('loss', ['mse', 'huber']))

        return self.build(X_train, y_train,
                          num_heads=num_heads,
                          hidden_size=hidden_size,
                          hidden_units=hidden_units,
                          dropout_rate=dropout_rate,
                          learning_rate=learning_rate,
                          loss_fn=loss_fn)