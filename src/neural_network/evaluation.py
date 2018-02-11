import datetime
import json

import tensorflow as tf
from PIL import Image
import os
import numpy as np

import glob

from neural_network.image_tools.preprocess import preprocess
from neural_network.load_data import dataset_loader
from tensorflow.contrib.slim.python.slim.nets import inception_v3

int_image_files = 0;


def dataloader_gen(img_path, batch_size=1):
    os_path_img = os.path.expanduser(img_path)
    list_fns_img = glob.glob(os_path_img)

    int_image_files = len(list_fns_img)
    print(len(list_fns_img))

    i = 0
    while (True):
        res = []
        lesion_classes = np.zeros([batch_size, 2])
        for j in range(batch_size):
            single_img_path = list_fns_img[i % len(list_fns_img)].replace("\\", "/")

            fn_name = "_".join(single_img_path.split('/')[-1].split("_")[0: 2])
            json_single_img_path = "/".join(single_img_path.split('/')[0: -2]) + "/Descriptions/" + fn_name

            # IMAGE
            image = Image.open(single_img_path)
            np_image = np.asarray(image)

            if np_image.shape[0] > np_image.shape[1]:
                np_image = np.rot90(np_image, axes=(-3, -2))

            res.append(np_image)

            # JSON
            json_file = json.load(open(json_single_img_path))

            # search for the lesion class
            clinical_class = json_file["meta"]["clinical"]["benign_malignant"]

            if clinical_class == "benign":
                lesion_classes[j, 0] = 1

            elif clinical_class == "malignant":
                lesion_classes[j, 1] = 1

            i = i + 1

        yield res, lesion_classes


def evaluate(img_path=None, snapshot_folder=None, eval_path=None):
    x = tf.placeholder(dtype=tf.float32, shape=[1, 542, 718, 3], name='input')
    y = tf.placeholder(dtype=tf.float32, shape=[1, 2], name='label')

    x_preprocessed = preprocess(x)

    net, endpoints = inception_v3.inception_v3(inputs=x_preprocessed, num_classes=2, is_training=True,
                                               dropout_keep_prob=0.8)

    gen = dataloader_gen(img_path)

    restorer = tf.train.Saver()  # load correct weights

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())

        restorer.restore(sess=sess, save_path=snapshot_folder + '/model.ckpt')

        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0

        for i in range(len(int_image_files)):
            img_input, label_input = gen.__next__()
            feed_dict = {x: img_input, y: label_input}
            result, label = sess.run([net, y], feed_dict=feed_dict)
            if (result[0][0] >= result[0][1]):
                result[0][0] = 1
                result[0][1] = 0
            else:
                result[0][0] = 0
                result[0][1] = 1

            result_set = set(result[0])
            label_set = set(label[0])

            if ((result_set == label_set) and (result_set == set([1, 0]))):
                true_negatives += 1
            elif ((result_set == label_set) and (result_set == set([0, 1]))):
                true_positives += 1
            elif ((result_set != label_set) and (result_set == set([1, 0]))):
                false_negatives += 1
            elif ((result_set != label_set) and (result_set == set([0, 1]))):
                false_positives += 1

        acc = (true_positives + true_negatives) / int_image_files

        with open(eval_path + 'eval.log', 'w') as f:
            eval_string = "TP: " + str(true_positives) + "\n TN: " + str(true_negatives) + "\n FP: " + \
                          str(false_positives) + "\n FN: " + str(false_negatives) \
                          + "\n Acc: " + str(acc)
            f.writelines(eval_string)
            print(eval_string)
