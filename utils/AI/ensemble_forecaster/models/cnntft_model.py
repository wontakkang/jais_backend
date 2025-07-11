# cnn_tft_model.py

import tensorflow as tf
from tensorflow import keras
from keras import layers

class CNNTFTModel:
    
    model_type = 'DL' # 딥러닝 모델
    def __init__(self, config):
        self.config = config

    def build(self, X_train, y_train,
              conv_filters=64,
              attention_heads=4,
              transformer_units=128,
              hidden_units=128,
              dropout_rate=0.1,
              learning_rate=1e-3,
              loss_fn='mse'):

        if hasattr(self.config, 'cnn_tft_params'):
            params = self.config.cnn_tft_params
            conv_filters = params.get('conv_filters', conv_filters)
            attention_heads = params.get('attention_heads', attention_heads)
            transformer_units = params.get('transformer_units', transformer_units)
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

        # ✅ 1. CNN 블록: Local pattern extraction
        x = keras.layers.Conv1D(filters=conv_filters, kernel_size=3, activation='relu', padding='same')(inputs)
        x = keras.layers.Conv1D(filters=conv_filters, kernel_size=3, activation='relu', padding='same')(x)
        x = keras.layers.LayerNormalization()(x)
        x = keras.layers.Dropout(dropout_rate)(x)

        # ✅ 2. Transformer 블록: Long-range dependency
        attn_output = keras.layers.MultiHeadAttention(num_heads=attention_heads, key_dim=conv_filters)(x, x)
        x = keras.layers.Add()([x, attn_output])  # Residual connection
        x = keras.layers.LayerNormalization()(x)

        # Transformer Feed Forward
        ff_output = keras.layers.Dense(transformer_units, activation='relu')(x)
        ff_output = keras.layers.Dense(conv_filters)(ff_output)
        x = keras.layers.Add()([x, ff_output])  # Residual connection
        x = keras.layers.LayerNormalization()(x)

        x = keras.layers.Dropout(dropout_rate)(x)

        # ✅ 3. Dense 블록
        x = keras.layers.Flatten()(x)
        x = keras.layers.Dense(hidden_units, activation='relu')(x)
        x = keras.layers.Dense(output_seq_len * output_features)(x)

        # ✅ 4. 출력
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
        attention_heads = hp.Choice('attention_heads', [2, 4, 8])
        transformer_units = hp.Choice('transformer_units', [64, 128, 256])
        hidden_units = hp.Choice('hidden_units', [64, 128, 256])
        dropout_rate = hp.Choice('dropout_rate', [0.0, 0.1, 0.2, 0.3])
        learning_rate = hp.Choice('learning_rate', [1e-2, 1e-3, 1e-4])
        loss_fn = hp.Choice('loss', ['mse', 'huber'])

        return self.build(X_train, y_train,
                          conv_filters=conv_filters,
                          attention_heads=attention_heads,
                          transformer_units=transformer_units,
                          hidden_units=hidden_units,
                          dropout_rate=dropout_rate,
                          learning_rate=learning_rate,
                          loss_fn=loss_fn)
