import numpy as np
import keras

class PatchTSTModel:
    
    model_type = 'DL' # 딥러닝 모델
    
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train, d_model=128, patch_len=16, stride=8, hidden_units=512, learning_rate=1e-3, loss_fn='mse'):
        if hasattr(self.config, 'patchtst_params'):
            params = self.config.patchtst_params
            d_model = params.get('d_model', d_model)
            patch_len = params.get('patch_len', patch_len)
            stride = params.get('stride', stride)
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

        x = keras.layers.Conv1D(d_model, patch_len, strides=stride, padding="causal")(inputs)
        x = keras.layers.LayerNormalization()(x)
        x = keras.layers.GlobalAveragePooling1D()(x)
        x = keras.layers.BatchNormalization()(x)
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
        hp_grid = self.config.hyperparameter_grids.get('PatchTSTModel', {})

        d_model = hp.Choice('d_model', hp_grid.get('d_model', [64, 128, 256]))
        patch_len = hp.Choice('patch_len', hp_grid.get('patch_len', [8, 16, 32]))
        stride = hp.Choice('stride', hp_grid.get('stride', [4, 8, 16]))
        hidden_units = hp.Choice('hidden_units', hp_grid.get('hidden_units', [32, 64, 128, 256, 512]))
        learning_rate = hp.Choice('learning_rate', hp_grid.get('learning_rate', [1e-2, 1e-3, 1e-4]))
        loss_fn = hp.Choice('loss', hp_grid.get('loss', ['mse', 'huber']))

        return self.build(X_train, y_train,
                          d_model=d_model,
                          patch_len=patch_len,
                          stride=stride,
                          hidden_units=hidden_units,
                          learning_rate=learning_rate,
                          loss_fn=loss_fn)
