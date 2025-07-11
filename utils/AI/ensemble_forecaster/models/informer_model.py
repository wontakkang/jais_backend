import numpy as np
import keras
class InformerModel:
    
    model_type = 'DL' # 딥러닝 모델
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train, d_model=128, n_heads=4, hidden_units=512, factor=5, dropout_rate=0.1, learning_rate=1e-3, loss_fn='mse'):
        if hasattr(self.config, 'informer_params'):
            params = self.config.informer_params
            d_model = params.get('d_model', d_model)
            n_heads = params.get('n_heads', n_heads)
            hidden_units = params.get('hidden_units', hidden_units)
            factor = params.get('factor', factor)
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

        x = keras.layers.Conv1D(d_model, kernel_size=factor, strides=factor, padding='causal')(inputs)
        x = keras.layers.LayerNormalization()(x) # 하나의 샘플(배치 안 하나) 에 대해 특성(feature)별로 정규화
        x = keras.layers.GlobalAveragePooling1D()(x) # 1D feature들을 평균내서 차원을 줄이는 층
        x = keras.layers.BatchNormalization()(x) # 배치 단위(여러 샘플) 로 평균과 분산을 계산해서 정규화
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
        hp_grid = self.config.hyperparameter_grids.get('InformerModel', {})
        d_model = hp.Choice('d_model', hp_grid.get('d_model', [64, 128, 256]))
        n_heads = hp.Choice('n_heads', hp_grid.get('n_heads', [2, 4, 8]))
        hidden_units = hp.Choice('hidden_units', hp_grid.get('hidden_units', [32, 64, 128, 256, 512]))
        factor = hp.Choice('factor', hp_grid.get('factor', [3, 5, 7]))
        dropout_rate = hp.Choice('dropout_rate', hp_grid.get('dropout_rate', [0.1, 0.2]))
        learning_rate = hp.Choice('learning_rate', hp_grid.get('learning_rate', [1e-2, 1e-3, 1e-4]))
        loss_fn = hp.Choice('loss', hp_grid.get('loss', ['mse', 'huber']))

        return self.build(X_train, y_train,
                          d_model=d_model,
                          n_heads=n_heads,
                          hidden_units=hidden_units,
                          factor=factor,
                          dropout_rate=dropout_rate,
                          learning_rate=learning_rate,
                          loss_fn=loss_fn)

