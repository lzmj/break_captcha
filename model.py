#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Author: _defined
@Time:  2019/8/6 16:38
@Description: 
"""
import os

from tensorflow.python.keras.layers import *
from tensorflow.python.keras.optimizers import Adam
from tensorflow.python.keras.models import Model
from tensorflow.python.keras.regularizers import l2
from tensorflow.python.keras import backend as K
from tensorflow.python.keras.utils import plot_model
from networks import (
    ResNet50, CNN5, BiGRU, BiLSTM
)
from settings import config

__all__ = ['build_model', 'test_model']


def ctc_lambda_func(args):
    y_pred, labels, input_length, label_length = args
    # the 2 is critical here since the first couple outputs of the RNN tend to be garbage
    y_pred = y_pred[:, :, :]
    return K.ctc_batch_cost(labels, y_pred, input_length, label_length)


def build_model():
    """
    build CNN-RNN model
    :return:
    """
    cnn_type = config.cnn if config.cnn in ['CNN5', 'ResNet50'] else 'CNN5'
    rnn_type = config.rnn if config.rnn in ['BiGRU', 'BiLSTM'] else 'BiLSTM'
    input_shape = (config.resize[0], config.resize[1], config.channel)
    inputs = Input(shape=input_shape)
    # CNN layers
    x = CNN5(inputs) if cnn_type == 'CNN5' else ResNet50(inputs)
    conv_shape = x.get_shape()
    x = Reshape(target_shape=(int(conv_shape[1]), int(conv_shape[2] * conv_shape[3])))(x)
    # x = Reshape(target_shape=(int(conv_shape[1]), int(conv_shape[2] * conv_shape[3])))(x)
    # concat Bi-RNN layers to encode and decode sequence
    x = BiLSTM(x, use_gpu=config.use_gpu) if rnn_type == 'BiLSTM' else BiGRU(x, use_gpu=config.use_gpu)
    predictions = TimeDistributed(Dense(config.n_class, kernel_initializer='he_normal', activation='softmax'))(x)
    base_model = Model(inputs=inputs, outputs=predictions)
    # CTC_loss
    labels = Input(name='the_labels', shape=[config.max_seq_len, ], dtype='float32')
    input_length = Input(name='input_length', shape=[1], dtype='int64')
    label_length = Input(name='label_length', shape=[1], dtype='int64')
    loss_out = Lambda(ctc_lambda_func, output_shape=(1,), name='ctc')(
        [predictions, labels, input_length, label_length])
    model = Model(inputs=[inputs, labels, input_length, label_length], outputs=[loss_out])
    model.compile(loss={'ctc': lambda y_true, y_pred: y_pred}, optimizer=Adam(lr=1e-4))
    if not os.path.exists('./plotModel'):
        os.makedirs('./plotModel')
    plot_model(model, './plotModel/{}-{}_model.png'.format(cnn_type, rnn_type), show_shapes=True)
    plot_model(base_model, './plotModel/{}-{}_base_model.png'.format(cnn_type, rnn_type), show_shapes=True)
    return model, base_model, int(conv_shape[1])


def test_model():
    inputs = Input((150, 50, 1))
    x = inputs
    for i in range(3):
        x = Convolution2D(32 * 2 ** i, (3, 3), activation='relu', padding='same',
                          kernel_regularizer=l2(0.01))(x)
        # x = Convolution2D(32*2**i, (3, 3), activation='relu')(x)
        x = BatchNormalization()(x)
        x = MaxPooling2D(pool_size=(2, 2))(x)
    x = Convolution2D(64, (3, 3), activation='relu', padding='same', kernel_regularizer=l2(0.01))(x)
    # x = Convolution2D(32*2**i, (3, 3), activation='relu')(x)
    x = BatchNormalization()(x)
    x = MaxPooling2D(pool_size=(2, 2))(x)

    conv_shape = x.get_shape()
    print(conv_shape)
    x = Reshape(target_shape=(int(conv_shape[1]) * int(conv_shape[2]), conv_shape[3]))(x)
    x = Dense(32, activation='relu')(x)
    '''加入gru'''

    gru_1 = GRU(64, return_sequences=True, kernel_initializer='he_normal', name='gru1')(x)
    gru_1b = GRU(64, return_sequences=True, go_backwards=True, kernel_initializer='he_normal', name='gru1_b')(x)
    gru1_merged = add([gru_1, gru_1b])

    gru_2 = GRU(64, return_sequences=True, kernel_initializer='he_normal', name='gru2')(gru1_merged)
    gru_2b = GRU(64, return_sequences=True, go_backwards=True, kernel_initializer='he_normal', name='gru2_b')(
        gru1_merged)
    x = concatenate([gru_2, gru_2b])
    x = Dropout(0.5)(x)
    predictions = Dense(37, kernel_initializer='he_normal', activation='softmax')(x)
    base_model = Model(inputs=inputs, outputs=predictions)

    '''CTC_loss'''
    labels = Input(name='the_labels', shape=[4, ], dtype='float32')
    input_length = Input(name='input_length', shape=[1], dtype='int64')
    label_length = Input(name='label_length', shape=[1], dtype='int64')
    loss_out = Lambda(ctc_lambda_func, output_shape=(1,), name='ctc')(
        [predictions, labels, input_length, label_length])
    model = Model(inputs=[inputs, labels, input_length, label_length], outputs=[loss_out])
    model.compile(loss={'ctc': lambda y_true, y_pred: y_pred}, optimizer='adam')
    plot_model(base_model, 'theirs.png', show_shapes=True)
    return model, base_model, int(conv_shape[1])
