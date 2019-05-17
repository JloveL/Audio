# Copyright 2017 The TensorFlow Authors All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

r"""A simple demonstration of running VGGish in inference mode.

This is intended as a toy example that demonstrates how the various building
blocks (feature extraction, model definition and loading, postprocessing) work
together in an inference context.

A WAV file (assumed to contain signed 16-bit PCM samples) is read in, converted
into log mel spectrogram examples, fed into VGGish, the raw embedding output is
whitened and quantized, and the postprocessed embeddings are optionally written
in a SequenceExample to a TFRecord file (using the same format as the embedding
features released in AudioSet).

Usage:
  # Run a WAV file through the model and print the embeddings. The model
  # checkpoint is loaded from vggish_model.ckpt and the PCA parameters are
  # loaded from vggish_pca_params.npz in the current directory.
  $ python vggish_inference_demo.py --wav_file /path/to/a/wav/file

  # Run a WAV file through the model and also write the embeddings to
  # a TFRecord file. The model checkpoint and PCA parameters are explicitly
  # passed in as well.
  $ python vggish_inference_demo.py --wav_file /home/atticus/PycharmProjects/ship/Data/ShipsEar/A1.wav
                                    --tfrecord_file /path/to/tfrecord/file \
                                    --checkpoint /path/to/model/checkpoint \
                                    --pca_params /path/to/pca/params

  # Run a built-in input (a sine wav) through the model and print the
  # embeddings. Associated model files are read from the current directory.
  $ python vggish_inference_demo.py


$ cd /Audio/Features
# Download data files into same directory as code.
$ curl -O https://storage.googleapis.com/audioset/vggish_model.ckpt
$ curl -O https://storage.googleapis.com/audioset/vggish_pca_params.npz
"""

from __future__ import print_function

import numpy as np
from scipy.io import wavfile
import six
import tensorflow as tf

import vggish_input
import vggish_params
import vggish_postprocess
import vggish_slim

flags = tf.app.flags

flags.DEFINE_string(
    'wav_file', None,
    'Path to a wav file. Should contain signed 16-bit PCM samples. '
    'If none is provided, a synthetic sound is used.')

flags.DEFINE_string(
    'checkpoint', 'vggish_model.ckpt',
    'Path to the VGGish checkpoint file.')

flags.DEFINE_string(
    'pca_params', 'vggish_pca_params.npz',
    'Path to the VGGish PCA parameters file.')

flags.DEFINE_string(
    'tfrecord_file', None,
    'Path to a TFRecord file where embeddings will be written.')

FLAGS = flags.FLAGS

import csv
import os
import librosa

genres = 'A B C D E'.split()
path = '/home/atticus/PycharmProjects/ship/Data/ShipsEar/ABCDE/'
header = 'filename'
for i in range(128):
    header += f' vgg{i}'
header += ' label'
header = header.split()


def main(_):
    # In this simple example, we run the examples from a single audio file through
    # the model. If none is provided, we generate a synthetic input.
    count = 0
    os.remove('ship_vgg.csv')
    file = open('ship_vgg.csv', 'w', newline='')
    with file:
        writer = csv.writer(file)
        writer.writerow(header)

    genres = 'A B C D E'.split()

    # Prepare a postprocessor to munge the model embeddings.
    pproc = vggish_postprocess.Postprocessor(FLAGS.pca_params)
    with tf.Graph().as_default(), tf.Session() as sess:
        # Define the model in inference mode, load the checkpoint, and
        # locate input and output tensors.
        vggish_slim.define_vggish_slim(training=False)
        vggish_slim.load_vggish_slim_checkpoint(sess, FLAGS.checkpoint)
        features_tensor = sess.graph.get_tensor_by_name(
            vggish_params.INPUT_TENSOR_NAME)
        embedding_tensor = sess.graph.get_tensor_by_name(
            vggish_params.OUTPUT_TENSOR_NAME)

        #######################
        # 对每一个文件抽取特征
        #######################

        for g in genres:
            for shipname in os.listdir(f'{path}/{g}'):
                print("shipname:", shipname)
                wav_file = f'{path}/{g}/{shipname}'
                y, sr = librosa.load(wav_file, sr=None)
                if int(len(y) / sr) < 1:
                    continue
                examples_batch = vggish_input.wavfile_to_examples(wav_file)
                print('examples_batch:', examples_batch.shape)

                # Run inference and postprocessing.
                [embedding_batch] = sess.run([embedding_tensor],
                                             feed_dict={features_tensor: examples_batch})
                print("embedding_batch:", len(embedding_batch))

                postprocessed_batch = pproc.postprocess(embedding_batch)
                print("postprocessed_batch:", len(postprocessed_batch))
                # print(postprocessed_batch)

                ####################
                # 写入csv
                ####################
                for embedding in postprocessed_batch:
                    count += 1
                    to_append = f'{shipname.split("-")[1].split("__")[0]}'  # 加上文件名
                    # A-15__10_07_13_radaUno_Pasa_1.wav
                    # 只保留文件ID ，eg. 15
                    for e in embedding:
                        to_append += f' {e}'  # 加上128维VGGish向量
                    to_append += f' {g}'  # 加上标签
                    file = open('ship_vgg.csv', 'a', newline='')
                    with file:
                        writer = csv.writer(file)
                        writer.writerow(to_append.split())
                        print(f'writing {count} VGGish feature...')


if __name__ == '__main__':
    tf.app.run()