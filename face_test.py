
# coding: utf-8

# ## Parameters

# In[1]:

#LAMBDA = 0.0
LAMBDA = 0.0001
CENTER_LOSS_ALPHA = 0.0
NUM_CLASSES = 30
checkpoint_dir = "./model_cache/"

# ## Import modules

# In[2]:

import os
import cv2
import numpy as np
import tensorflow as tf
import tflearn
#from batch_loader import BatchLoader
import numpy.random as nr
from random import shuffle

"""
Batch Loader by Donny You
"""

class BatchLoader(object):

    def __init__(self, file_path, batch_size):
        self.batch_size = batch_size
        self.labels, self.im_list = self.image_dir_processor(file_path)
        self.idx = 0
        self.data_num = len(self.labels)
        self.rnd_list = np.arange(self.data_num)
        #shuffle(self.rnd_list)

    def next_batch(self):
        batch_images = []
        batch_labels = []

        for i in xrange (self.batch_size):
            if self.idx != self.data_num:
                cur_idx = self.rnd_list[self.idx]
                im_path = self.im_list[cur_idx]
                image = cv2.imread(im_path)
                #print image.shape
                #image = cv2.resize(image, (100, 100), interpolation=cv2.INTER_CUBIC)
                batch_images.append(image)
                batch_labels.append(self.labels[cur_idx])

                self.idx +=1
            else:
                self.idx = 0
                shuffle(self.rnd_list)

        batch_images = np.array(batch_images).astype(np.float32)
        batch_labels = np.array(batch_labels).astype(np.float32)
        return batch_images, batch_labels, im_path
        
    def image_dir_processor(self, file_path):
        labels = []
        im_path_list = []
        if not os.path.exists(file_path):
            print ("File %s not exists." % file_path)
            exit()

        with open(file_path, "r") as fr:
            for line in fr.readlines():
                terms = line.rstrip().split()
                label = int(terms[1])
                im_path_list.append(terms[0])
                labels.append(label)

        return labels, im_path_list



slim = tf.contrib.slim
os.environ['CUDA_VISIBLE_DEVICES'] = '0'

train_batch_loader = BatchLoader("ORL_face_dataset_train.txt", 50)
#test_batch_loader = BatchLoader("ORL_face_dataset_validation.txt", 30)
test_batch_loader = BatchLoader("ORL_face_dataset_test.txt", 1)
#test_batch_loader = BatchLoader("ORL_face_dataset_test_probe.txt", 1)
# ## Construct network

# In[3]:

with tf.name_scope('input'):
    input_images = tf.placeholder(tf.float32, shape=(None,112,92,3), name='input_images')
    labels = tf.placeholder(tf.int64, shape=(None), name='labels')
    
global_step = tf.Variable(0, trainable=False, name='global_step')


# In[4]:

def get_center_loss(features, labels, alpha, num_classes):
    """获取center loss及center的更新op
    
    Arguments:
        features: Tensor,表征样本特征,一般使用某个fc层的输出,shape应该为[batch_size, feature_length].
        labels: Tensor,表征样本label,非one-hot编码,shape应为[batch_size].
        alpha: 0-1之间的数字,控制样本类别中心的学习率,细节参考原文.
        num_classes: 整数,表明总共有多少个类别,网络分类输出有多少个神经元这里就取多少.
    
    Return：
        loss: Tensor,可与softmax loss相加作为总的loss进行优化.
        centers: Tensor,存储样本中心值的Tensor，仅查看样本中心存储的具体数值时有用.
        centers_update_op: op,用于更新样本中心的op，在训练时需要同时运行该op，否则样本中心不会更新
    """
    # 获取特征的维数，例如256维
    # print features.get_shape()
    len_features = features.get_shape()[1]
    # 建立一个Variable,shape为[num_classes, len_features]，用于存储整个网络的样本中心，
    # 设置trainable=False是因为样本中心不是由梯度进行更新的
    centers = tf.get_variable('centers', [num_classes, len_features], dtype=tf.float32,
        initializer=tf.constant_initializer(0), trainable=False)
    # 将label展开为一维的，输入如果已经是一维的，则该动作其实无必要
    labels = tf.reshape(labels, [-1])
    
    # 根据样本label,获取mini-batch中每一个样本对应的中心值
    centers_batch = tf.gather(centers, labels)
    # 计算loss
    loss = tf.nn.l2_loss(features - centers_batch)
    
    # 当前mini-batch的特征值与它们对应的中心值之间的差
    diff = centers_batch - features
    
    # 获取mini-batch中同一类别样本出现的次数,了解原理请参考原文公式(4)
    unique_label, unique_idx, unique_count = tf.unique_with_counts(labels)
    appear_times = tf.gather(unique_count, unique_idx)
    appear_times = tf.reshape(appear_times, [-1, 1])
    
    diff = diff / tf.cast((1 + appear_times), tf.float32)
    diff = alpha * diff
    
    centers_update_op = tf.scatter_sub(centers, labels, diff)
    
    return loss, centers, centers_update_op


# In[5]:



def inference(input_images):
    with slim.arg_scope([slim.conv2d], 
                         activation_fn=tflearn.prelu, stride=1, padding='SAME',
                         weights_initializer=tf.truncated_normal_initializer(stddev=0.01)):
                         # weights_initializer=tf.contrib.layers.xavier_initializer()):
        x = slim.conv2d(input_images, 32, [3, 3],
                        weights_initializer=tf.contrib.layers.xavier_initializer(),
                        padding='VALID', scope='conv1a')

        x = slim.conv2d(x, 64, [3, 3], 
                        weights_initializer=tf.contrib.layers.xavier_initializer(), 
                        padding='VALID', scope='conv1b')

        pool1b = slim.max_pool2d(x, [2, 2], stride=2, padding='VALID', scope='pool1b')

        conv2_1 = slim.conv2d(pool1b, 64, [3, 3], scope='conv2_1')
        conv2_2 = slim.conv2d(conv2_1, 64, [3, 3], scope='conv2_2')
        res2_2 = pool1b + conv2_2
        conv2 = slim.conv2d(res2_2, 128, [3, 3],
                        weights_initializer=tf.contrib.layers.xavier_initializer(),
                        padding='VALID', scope='conv2')

        pool2 = slim.max_pool2d(conv2, [2, 2], stride=2, padding='VALID', scope='pool2')
        conv3_1 = slim.conv2d(pool2, 128, [3, 3], scope='conv3_1')
        conv3_2 = slim.conv2d(conv3_1, 128, [3, 3], scope='conv3_2')
        res3_2 = pool2 + conv3_2

        conv3_3 = slim.conv2d(res3_2, 128, [3, 3], scope='conv3_3')
        conv3_4 = slim.conv2d(conv3_3, 128, [3, 3], scope='conv3_4')
        res3_4 = res3_2 + conv3_4

        conv3 = slim.conv2d(res3_4, 256, [3, 3],
                        weights_initializer=tf.contrib.layers.xavier_initializer(),
                        padding='VALID', scope='conv3')
        pool3 = slim.max_pool2d(conv3, [2, 2], stride=2, padding='VALID', scope='pool3')
        conv4_1 = slim.conv2d(pool3, 256, [3, 3], scope='conv4_1')
        conv4_2 = slim.conv2d(conv4_1, 256, [3, 3], scope='conv4_2')
        res4_2 = pool3 + conv4_2

        conv4_3 = slim.conv2d(res4_2, 256, [3, 3], scope='conv4_3')
        conv4_4 = slim.conv2d(conv4_3, 256, [3, 3], scope='conv4_4')
        res4_4 = res4_2 + conv4_4

        conv4_5 = slim.conv2d(res4_4, 256, [3, 3], scope='conv4_5')
        conv4_6 = slim.conv2d(conv4_5, 256, [3, 3], scope='conv4_6')
        res4_6 = res4_4 + conv4_6

        conv4_7 = slim.conv2d(res4_6, 256, [3, 3], scope='conv4_7')
        conv4_8 = slim.conv2d(conv4_7, 256, [3, 3], scope='conv4_8')
        res4_8 = res4_6 + conv4_8

        conv4_9 = slim.conv2d(res4_8, 256, [3, 3], scope='conv4_9')
        conv4_10 = slim.conv2d(conv4_9, 256, [3, 3], scope='conv4_10')
        res4_10 = res4_8 + conv4_10

        conv4 = slim.conv2d(res4_10, 512, [3, 3],
                        weights_initializer=tf.contrib.layers.xavier_initializer(),
                        padding='VALID', scope='conv4')
        pool4 = slim.max_pool2d(conv4, [2, 2], stride=2, padding='VALID', scope='pool4')
        
        conv5_1 = slim.conv2d(pool4, 512, [3, 3], scope='conv5_1')
        conv5_2 = slim.conv2d(conv5_1, 512, [3, 3], scope='conv5_2')
        res5_2 = pool4 + conv5_2

        conv5_3 = slim.conv2d(res5_2, 512, [3, 3], scope='conv5_3')
        conv5_4 = slim.conv2d(conv5_3, 512, [3, 3], scope='conv5_4')
        res5_4 = res5_2 + conv5_4

        conv5_5 = slim.conv2d(res5_4, 512, [3, 3], scope='conv5_5')
        conv5_6 = slim.conv2d(conv5_5, 512, [3, 3], scope='conv5_6')
        res5_6 = res5_4 + conv5_6
        res5_6 = slim.flatten(res5_6, scope='flatten')
        feature = slim.fully_connected(res5_6, num_outputs=512, activation_fn=None, 
                            weights_initializer=tf.contrib.layers.xavier_initializer(), scope='fc1')

        x = slim.fully_connected(feature, num_outputs=NUM_CLASSES, activation_fn=None, scope='fc2')
    
    return x, feature


# In[6]:

def build_network(input_images, labels, ratio=0.5):
    logits, features = inference(input_images)
    
    with tf.name_scope('loss'):
        with tf.name_scope('center_loss'):
            center_loss, centers, centers_update_op = get_center_loss(features, labels, CENTER_LOSS_ALPHA, NUM_CLASSES)
        with tf.name_scope('softmax_loss'):
            softmax_loss = tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(labels=labels, logits=logits))
        with tf.name_scope('total_loss'):
            total_loss = softmax_loss + ratio * center_loss
    
    with tf.name_scope('acc'):
        accuracy = tf.reduce_mean(tf.cast(tf.equal(tf.arg_max(logits, 1), labels), tf.float32))
    '''
    with tf.name_scope('loss/'):
        tf.summary.scalar('CenterLoss', center_loss)
        tf.summary.scalar('SoftmaxLoss', softmax_loss)
        tf.summary.scalar('TotalLoss', total_loss)
    '''
    return logits, features, total_loss, accuracy, centers_update_op, center_loss, softmax_loss


# In[7]:

logits, features, total_loss, accuracy, centers_update_op, center_loss, softmax_loss = build_network(input_images, labels, ratio=LAMBDA)


# ## Prepare data

# In[8]:

# mnist = input_data.read_data_sets('/tmp/mnist', reshape=False)


# ## Optimizer

# In[9]:

optimizer = tf.train.AdamOptimizer(0.001)


# In[10]:

with tf.control_dependencies([centers_update_op]):
    train_op = optimizer.minimize(total_loss, global_step=global_step)


# ## Session and Summary

# In[11]:

summary_op = tf.summary.merge_all()


# In[12]:

sess = tf.Session()
sess.run(tf.global_variables_initializer())
writer = tf.summary.FileWriter('/tmp/mnist_log', sess.graph)


# ## Train
# In[14]:

#sess = tf.Session()
#init_op = tf.global_variables_initializer()
#sess.run(init_op)
saver =tf.train.Saver()
saver.restore(sess,'model_cache/model.ckpt-1200')
#image = cv2.imread("test_file/9.BMP")
#print image
for i in range(100):
    batch_images, batch_labels, im_path = test_batch_loader.next_batch()
    vali_image = (batch_images - 127.5) * 0.0078125
    vali_features = sess.run(
        features,
        feed_dict={
            input_images: vali_image,
            labels: batch_labels
        })
    #print vali_features.shape
    #print vali_features
    #print im_path
    words=im_path.split('/')
    #index_face=words[].split('/')
    feature_save_folder='face_feature/'+words[1]
    feature_save_name='face_feature/'+words[1]+'/'+words[2].split('.')[0]+'.npy'
    print (feature_save_name)
    if not os.path.exists(feature_save_folder):
        os.makedirs(feature_save_folder)
    np.save(feature_save_name, vali_features)

#c = np.load(feature_save_name)
#print c

sess.close()

