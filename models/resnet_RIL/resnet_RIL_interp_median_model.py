""" THIS FILE SUPPORTS THE GENERATION OF NETWORK SKELETONS """

# Import tensorflow modules
import tensorflow as tf
from tensorflow.contrib.rnn import static_rnn

from resnet_RIL_interp_preprocessing import preprocess

# Import math and numpy modules
import numpy as np

# Import HDF5
import h5py

import os

import sys
sys.path.append('../..')
from layers_utils import *

from load_dataset import load_dataset as load_data



class ResNet_RIL_Interp_Median():

    def __init__(self, verbose=True):
        self.verbose=verbose
        self.name = 'resnet_RIL_interp_median'
        print "resnet RIL interp median initialized"




    def _rate_invariance_layer(self, inputs, params, sets, K, L):

        # Parameter definitions are taken as mean ($\psi(\cdot)$) of input estimates
        sample_alpha_tick = tf.nn.top_k(params[:,0], params[:,0].get_shape()[0]//2).values[params[:,0].get_shape()[0]//2 - 1]
        sample_phi_tick   = tf.nn.top_k(params[:,1], params[:,1].get_shape()[0]//2).values[params[:,1].get_shape()[0]//2 - 1]
        #return tf.reshape(tf.tile([sampleOffset], [7526400]), (50,224,224,3))

        # Extract shape of input signal
        frames, shp_h, shp_w, channel = inputs.get_shape().as_list()
        #return tf.reshape(tf.tile([tf.to_float(tf.to_int32(sampleOffset))], [7526400]), (50,224,224,3))

        # Offset scaling to match inputs temporal dimension
        sample_phi_tick = sample_phi_tick * tf.cast((sets*K) - L, tf.float32)
        #return tf.reshape(tf.tile([sampleOffset], [7526400]), (50,224,224,3))

        phi_tick = tf.tile(sample_phi_tick, [L])

        # Generate indices for output
        output_idx = tf.range(start=1., limit=float(L)+1., delta=1., dtype=tf.float32)
        #return tf.reshape(tf.tile(sampleOffset, [7526400]), (50,224,224,3))
        #return tf.reshape(tf.tile(outputIdx, [150528]), (50,224,224,3))

        output_idx = tf.slice(output_idx, [0],[L])
        #return tf.reshape(tf.tile(outputIdx, [150528]), (50,224,224,3))

        # Add offset to the output indices
        output_idx = output_idx + phi_tick
        #return tf.reshape(tf.tile(outputIdx, [150528]), (50,224,224,3))

        # Sampling parameter scaling to match inputs temporal dimension
        alpha_tick = sample_alpha_tick * tf.cast(K * sets, tf.float32) / (float(L) + sample_phi_tick)
        #return tf.reshape(tf.tile(const, [7526400]), (50,224,224,3))

        # Include sampling parameter to correct output indices
        output_idx = tf.multiply(tf.tile(alpha_tick, [L]), output_idx)
        #return tf.reshape(tf.tile(outputIdx, [150528]), (50,224,224,3))

        # Clip output index values to >= 1 and <=N (valid cases only)
        output_idx = tf.clip_by_value(output_idx, 1., tf.cast(sets*K, tf.float32))


        # Create x0 and x1 float
        x0 = tf.clip_by_value(tf.floor(output_idx), 1., tf.cast(sets*K, tf.float32)-1.)
        x1 = tf.clip_by_value(tf.floor(output_idx+1.), 2., tf.cast(sets*K, tf.float32))


        # Deltas :
        d1 = (output_idx - x0)
        d2 = (x1 - x0)
        d1 = tf.reshape(tf.tile(d1, [224*224*3]), [50,224,224,3])
        d2 = tf.reshape(tf.tile(d2, [224*224*3]), [50,224,224,3])


        # Create x0 and x1 indices
        output_idx_0 = tf.cast(tf.floor(output_idx), 'int32')
        output_idx_1 = tf.cast(tf.ceil(output_idx), 'int32')
        output_idx   = tf.cast(output_idx, 'int32')

        # Create y0 and y1 outputs
        output_0 = tf.gather(inputs, output_idx_0-1)
        output_1 = tf.gather(inputs, output_idx_1-1)
        output   = tf.gather(inputs, output_idx-1)

        d3 = output_1 - output_0

        output = tf.add_n([(d1/d2)*d3, output_0])

        output = tf.reshape(output, (L, shp_h, shp_w, channel), name='RIlayeroutput')

        return output




    def _LSTM(self, inputs, seqLength, featSize, cellSize=1024, isTraining=False):

        # Unstack input tensor to match shape:
        # list of n_time_steps items, each item of size (batch_size x featSize)
        inputs = tf.reshape(inputs, [-1,1,featSize])
        inputs = tf.unstack(inputs, seqLength, axis=0)

        # LSTM cell definition
        lstm_cell = tf.contrib.rnn.BasicLSTMCell(cellSize)
        outputs, states = static_rnn(lstm_cell, inputs, dtype=tf.float32)

        # Condense output shape from:
        # list of n_time_steps itmes, each item of size (batch_size x cellSize)
        # To:
        # Tensor: [(n_time_steps x 1), cellSize] (Specific to our case)
        outputs = tf.stack(outputs)
        outputs = tf.reshape(outputs,[-1,cellSize])


        return outputs

    def _conv_block(self, nFilters, kernelSize, name, layerNumbers, inputLayer, dataDict, strides=2, weight_decay=0.0):

        layers = {}

        # Conv block
        layers[layerNumbers[0]] = conv_layer(input_tensor=inputLayer,
                filter_dims=[1,1,nFilters[0]], stride_dims=[strides,strides],
                padding = 'VALID',
                name='res'+name+'_branch2a',
                kernel_init=tf.constant_initializer(dataDict['res'+name+'_branch2a']['res'+name+'_branch2a_W:0'].value),
                bias_init=tf.constant_initializer(dataDict['res'+name+'_branch2a']['res'+name+'_branch2a_b:0'].value),
                weight_decay = weight_decay, non_linear_fn=None)

        layers[layerNumbers[1]] = tf.layers.batch_normalization(layers[layerNumbers[0]],
                name='bn'+name+'_branch2a',
                moving_mean_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_running_mean:0'].value),
                moving_variance_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_running_std:0'].value),
                beta_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_beta:0'].value),
                gamma_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_gamma:0'].value))

        layers[layerNumbers[2]] = conv_layer(input_tensor=tf.nn.relu(layers[layerNumbers[1]]),
                filter_dims=[kernelSize, kernelSize, nFilters[1]], padding='SAME',
                name='res'+name+'_branch2b',
                kernel_init=tf.constant_initializer(dataDict['res'+name+'_branch2b']['res'+name+'_branch2b_W:0'].value),
                bias_init=tf.constant_initializer(dataDict['res'+name+'_branch2b']['res'+name+'_branch2b_b:0'].value),
                weight_decay = weight_decay, non_linear_fn=None)

        layers[layerNumbers[3]] = tf.layers.batch_normalization(layers[layerNumbers[2]],
                name='bn'+name+'_branch2b',
                moving_mean_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_running_mean:0'].value),
                moving_variance_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_running_std:0'].value),
                beta_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_beta:0'].value),
                gamma_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_gamma:0'].value))

        layers[layerNumbers[4]] = conv_layer(input_tensor=tf.nn.relu(layers[layerNumbers[3]]),
                filter_dims=[1,1,nFilters[2]], padding = 'VALID',
                name='res'+name+'_branch2c',
                kernel_init=tf.constant_initializer(dataDict['res'+name+'_branch2c']['res'+name+'_branch2c_W:0'].value),
                bias_init=tf.constant_initializer(dataDict['res'+name+'_branch2c']['res'+name+'_branch2c_b:0'].value),
                weight_decay = weight_decay, non_linear_fn=None)

        layers[layerNumbers[5]] = tf.layers.batch_normalization(layers[layerNumbers[4]],
                name='bn'+name+'_branch2c',
                moving_mean_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_running_mean:0'].value),
                moving_variance_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_running_std:0'].value),
                beta_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_beta:0'].value),
                gamma_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_gamma:0'].value))

        # Shortcuts
        layers[layerNumbers[6]] = conv_layer(input_tensor=inputLayer,
                filter_dims=[1,1,nFilters[2]], stride_dims=[strides, strides],
                padding = 'VALID',
                name='res'+name+'_branch1',
                kernel_init=tf.constant_initializer(dataDict['res'+name+'_branch1']['res'+name+'_branch1_W:0'].value),
                bias_init=tf.constant_initializer(dataDict['res'+name+'_branch1']['res'+name+'_branch1_b:0'].value),
                weight_decay = weight_decay, non_linear_fn=None)

        layers[layerNumbers[7]] = tf.layers.batch_normalization(layers[layerNumbers[6]],
                name='bn'+name+'_branch1',
                moving_mean_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch1']['bn'+name+'_branch1_running_mean:0'].value),
                moving_variance_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch1']['bn'+name+'_branch1_running_std:0'].value),
                beta_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch1']['bn'+name+'_branch1_beta:0'].value),
                gamma_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch1']['bn'+name+'_branch1_gamma:0'].value))

        # END OF CONV BLOCK

        layers[layerNumbers[8]] = tf.nn.relu(tf.add(layers[layerNumbers[5]],layers[layerNumbers[7]]))

        return layers


    def _identity_block(self, nFilters, kernelSize, name, layerNumbers, inputLayer, dataDict, weight_decay=0.0):

        layers = {}

        # Identity block
        layers[layerNumbers[0]] = conv_layer(input_tensor=inputLayer,
                filter_dims=[1, 1, nFilters[0]], padding='VALID',
                name='res'+name+'_branch2a',
                kernel_init=tf.constant_initializer(dataDict['res'+name+'_branch2a']['res'+name+'_branch2a_W:0'].value),
                bias_init=tf.constant_initializer(dataDict['res'+name+'_branch2a']['res'+name+'_branch2a_b:0'].value),
                weight_decay = weight_decay, non_linear_fn=None)

        layers[layerNumbers[1]] = tf.layers.batch_normalization(layers[layerNumbers[0]],
                name='bn'+name+'_branch2a',
                moving_mean_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_running_mean:0'].value),
                moving_variance_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_running_std:0'].value),
                beta_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_beta:0'].value),
                gamma_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2a']['bn'+name+'_branch2a_gamma:0'].value))

        layers[layerNumbers[2]] = conv_layer(input_tensor=tf.nn.relu(layers[layerNumbers[1]]),
                filter_dims=[kernelSize, kernelSize, nFilters[1]], padding='SAME',
                name='res'+name+'_branch2b',
                kernel_init=tf.constant_initializer(dataDict['res'+name+'_branch2b']['res'+name+'_branch2b_W:0'].value),
                bias_init=tf.constant_initializer(dataDict['res'+name+'_branch2b']['res'+name+'_branch2b_b:0'].value),
                weight_decay = weight_decay, non_linear_fn=None)

        layers[layerNumbers[3]] = tf.layers.batch_normalization(layers[layerNumbers[2]],
                name='bn'+name+'_branch2b',
                moving_mean_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_running_mean:0'].value),
                moving_variance_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_running_std:0'].value),
                beta_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_beta:0'].value),
                gamma_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2b']['bn'+name+'_branch2b_gamma:0'].value))

        layers[layerNumbers[4]] = conv_layer(input_tensor=tf.nn.relu(layers[layerNumbers[3]]),
                filter_dims=[1,1,nFilters[2]], padding='VALID',
                name='res'+name+'_branch2c',
                kernel_init=tf.constant_initializer(dataDict['res'+name+'_branch2c']['res'+name+'_branch2c_W:0'].value),
                bias_init=tf.constant_initializer(dataDict['res'+name+'_branch2c']['res'+name+'_branch2c_b:0'].value),
                weight_decay = weight_decay, non_linear_fn=None)

        layers[layerNumbers[5]] = tf.layers.batch_normalization(layers[layerNumbers[4]],
                name='bn'+name+'_branch2c',
                moving_mean_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_running_mean:0'].value),
                moving_variance_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_running_std:0'].value),
                beta_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_beta:0'].value),
                gamma_initializer=tf.constant_initializer(dataDict['bn'+name+'_branch2c']['bn'+name+'_branch2c_gamma:0'].value))

        # END OF IDENTITY BLOCK

        layers[layerNumbers[6]] = tf.nn.relu(tf.add(layers[layerNumbers[5]],inputLayer))

        return layers

    def inference(self, inputs, isTraining, inputDims, outputDims, seqLength, scope, K, J, dropoutRate = 0.5, return_layer='logits', dataDict=None, cpuId = 0, weight_decay=0.0):

        ############################################################################
        #                       Creating ResNet50 Network Layers                   #
        ############################################################################

        print('Generating RESNET RIL network layers')
        dataDict = h5py.File('/z/home/erichof/TF_Activity_Recognition_Framework/models/resnet/resnet50_weights_tf_dim_ordering_tf_kernels.h5','r')

        with tf.name_scope(scope, 'resnet', [inputs]):
            layers = {}





            # Input shape:  [(K frames in a set x J number of sets) x Height x Width x Channels]
            # Output shape: [(K frames in a set x J number of sets) x Height x Width x 32]



            layers['Conv1'] = conv_layer(input_tensor=inputs,
                    filter_dims=[7, 7, 64], stride_dims=[2,2],
                    padding = 'VALID',
                    name='Conv1',
                    kernel_init=tf.constant_initializer(dataDict['conv1']['conv1_W:0'].value),
                    bias_init=tf.constant_initializer(dataDict['conv1']['conv1_b:0'].value),
                    weight_decay = weight_decay, non_linear_fn=None)

            layers['Conv1_bn'] = tf.layers.batch_normalization(layers['Conv1'],
                    name='bn_Conv1',
                    moving_mean_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_running_mean:0'].value),
                    moving_variance_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_running_std:0'].value),
                    beta_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_beta:0'].value),
                    gamma_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_gamma:0'].value))


            layers['Conv2'] = conv_layer(input_tensor=layers['Conv1_bn'],
                    filter_dims=[5, 5, 64], stride_dims=[2,2],
                    padding = 'VALID',
                    name='Conv2',
                    weight_decay = weight_decay, non_linear_fn=tf.nn.relu)


            layers['Reshape1'] = tf.reshape(layers['Conv2'], (-1, K, 53, 53, 64))

            layers['Dimshuffle1'] = tf.transpose(layers['Reshape1'], (0,2,3,4,1))

            layers['Reshape2'] = tf.reshape(layers['Dimshuffle1'], (-1, 64*K))



            layers['FC1'] = fully_connected_layer(input_tensor=layers['Reshape2'],
                    out_dim=512, non_linear_fn=tf.nn.relu,
                    name='FC1', weight_decay=weight_decay)


            layers['Reshape3'] = tf.reshape(layers['FC1'], (-1, 53, 53, 64))

            layers['Reshape4'] = tf.reshape(layers['Reshape3'], (-1, 53*53*64))


            layers['FC2'] = fully_connected_layer(input_tensor=layers['Reshape4'],
                    out_dim=2, non_linear_fn=tf.nn.sigmoid,
                    name='FC2', weight_decay=weight_decay)

            layers['RIlayer'] = self._rate_invariance_layer(inputs=inputs, params=layers['FC2'], sets=J, L=seqLength, K=K)




 #           import pdb; pdb.set_trace()
#            layers['RIlayer'] = tf.reshape(tf.tile(layers['FC2'][0], [3763200]), (50,224,224,3))



            layers['1'] = conv_layer(input_tensor=layers['RIlayer'],
                    filter_dims=[7, 7, 64], stride_dims=[2,2],
                    padding = 'VALID',
                    name='conv1',
                    kernel_init=tf.constant_initializer(dataDict['conv1']['conv1_W:0'].value),
                    bias_init=tf.constant_initializer(dataDict['conv1']['conv1_b:0'].value),
                    weight_decay = weight_decay, non_linear_fn=None)

            layers['2'] = tf.layers.batch_normalization(layers['1'],
                    name='bn_conv1',
                    moving_mean_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_running_mean:0'].value),
                    moving_variance_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_running_std:0'].value),
                    beta_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_beta:0'].value),
                    gamma_initializer=tf.constant_initializer(dataDict['bn_conv1']['bn_conv1_gamma:0'].value))

            layers['3'] = max_pool_layer(tf.nn.relu(layers['2']),
                    filter_dims=[3, 3], stride_dims=[2,2], name='pool1', padding='VALID')


            layers.update(self._conv_block([64,64,256], kernelSize=3, name='2a', layerNumbers=['4','5','6','7','8','9','10','11','12'],
                            inputLayer=layers['3'], strides=1, dataDict=dataDict))

            layers.update(self._identity_block([64,64,256], kernelSize=3, name='2b', layerNumbers=['13','14','15','16','17','18','19'],
                            inputLayer=layers['12'], dataDict=dataDict))

            layers.update(self._identity_block([64,64,256], kernelSize=3, name='2c', layerNumbers=['20','21','22','23','24','25','26'],
                            inputLayer=layers['19'], dataDict=dataDict))

            #########
            layers.update(self._conv_block([128,128,512], kernelSize=3, name='3a', layerNumbers=['27','28','29','30','31','32','33','34','35'],
                            inputLayer=layers['26'], dataDict=dataDict))

            layers.update(self._identity_block([128,128,512], kernelSize=3, name='3b', layerNumbers=['36','37','38','39','40','41','42'],
                            inputLayer=layers['35'], dataDict=dataDict))

            layers.update(self._identity_block([128,128,512], kernelSize=3, name='3c', layerNumbers=['43','44','45','46','47','48','49'],
                            inputLayer=layers['42'], dataDict=dataDict))

            layers.update(self._identity_block([128,128,512], kernelSize=3, name='3d', layerNumbers=['50','51','52','53','54','55','56'],
                            inputLayer=layers['49'], dataDict=dataDict))

            #########
            layers.update(self._conv_block([256,256,1024], kernelSize=3, name='4a', layerNumbers=['57','58','59','60','61','62','63','64','65'],
                            inputLayer=layers['56'], dataDict=dataDict))

            layers.update(self._identity_block([256,256,1024], kernelSize=3, name='4b', layerNumbers=['66','67','68','69','70','71','72'],
                            inputLayer=layers['65'], dataDict=dataDict))

            layers.update(self._identity_block([256,256,1024], kernelSize=3, name='4c', layerNumbers=['73','74','75','76','77','78','79'],
                            inputLayer=layers['72'], dataDict=dataDict))

            layers.update(self._identity_block([256,256,1024], kernelSize=3, name='4d', layerNumbers=['80','81','82','83','84','85','86'],
                            inputLayer=layers['79'], dataDict=dataDict))

            layers.update(self._identity_block([256,256,1024], kernelSize=3, name='4e', layerNumbers=['87','88','89','90','91','92','93'],
                            inputLayer=layers['86'], dataDict=dataDict))

            layers.update(self._identity_block([256,256,1024], kernelSize=3, name='4f', layerNumbers=['94','95','96','97','98','99','100'],
                            inputLayer=layers['93'], dataDict=dataDict))

            #########
            layers.update(self._conv_block([512,512,2048], kernelSize=3, name='5a', layerNumbers=['101','102','103','104','105','106','107','108','109'],
                            inputLayer=layers['100'], dataDict=dataDict))

            layers.update(self._identity_block([512,512,2048], kernelSize=3, name='5b', layerNumbers=['110','111','112','113','114','115','116'],
                            inputLayer=layers['109'], dataDict=dataDict))

            layers.update(self._identity_block([512,512,2048], kernelSize=3, name='5c', layerNumbers=['117','118','119','120','121','122','123'],
                            inputLayer=layers['116'], dataDict=dataDict))

            layers['124'] = tf.reduce_mean(layers['123'], reduction_indices=[1,2], name='avg_pool')
            layers['125'] = self._LSTM(layers['124'], seqLength, featSize=2048, cellSize=512, isTraining=isTraining)

            layers['126'] = tf.layers.dropout(layers['125'], training=isTraining, rate=0.5)

            layers['logits'] = fully_connected_layer(input_tensor=layers['126'],
                    out_dim=outputDims, non_linear_fn=None,
                    name='logits', weight_decay=weight_decay)

            return layers[return_layer]



    def preprocess(self, index, Data, labels, size, isTraining):
        return preprocess(index, Data, labels, size, isTraining)

    def loss(self, logits, labels):
        labels = tf.cast(labels, tf.int64)
        crossEntropyLoss = tf.losses.sparse_softmax_cross_entropy(labels=labels[:labels.shape[0].value/2],
                        logits=logits[:logits.shape[0].value/2,:])
        return crossEntropyLoss













if __name__=="__main__":

    from tensorflow.python.ops import clip_ops
    from tensorflow.python.ops import control_flow_ops
    from tensorflow.python.ops import variable_scope as vs
    from tensorflow.python.ops import variables as vars_
    from tensorflow.python.ops import init_ops
    import os
    with tf.name_scope('my_scope') as scope:

        #path = os.path.join('/z/home/madantrg/RILCode/Code_TF_ND/ExperimentBaseline','resnet50_weights_tf_dim_ordering_tf_kernels.h5')
        #data_dict = h5py.File(path,'r')

        #network = _gen_resnet50_baseline1_network(x, True, data_dict, 35, 51)
        model = ResNet_RIL()
    #    import pdb; pdb.set_trace()

        lr = 0.001



        outputDims = 101

        fName = 'testlist'
        dataset = 'HMDB51'

        if fName == 'testlist':
            if dataset == 'UCF101':
                totalVids = 3783
            else:
                totalVids = 1530
                outputDims = 51
            inputDims = 250
        else:
            if dataset=='UCF101':
                totalVids = 9537
            else:
                totalVids = 3570
                outputDims = 51
            inputDims = 125



        k=25

        j_value=[inputDims/k]

        seqLength = 50
        isTraining = True


        global_step = tf.Variable(0, name='global_step', trainable=False)
        x_placeholder = tf.placeholder(tf.float32, shape=(inputDims, 224,224,3))
        y_placeholder = tf.placeholder(tf.int32, [seqLength])
        j_placeholder = tf.placeholder(tf.int32, [1])


        logits = model.inference(x_placeholder, isTraining, inputDims, outputDims, seqLength, scope, k, j_placeholder)

        slogits = tf.nn.softmax(logits)
        sess = tf.Session()
        sess.run(tf.global_variables_initializer())
        # Define Optimizer
        optimizer = lambda lr: tf.train.MomentumOptimizer(learning_rate=lr, momentum=0.9)
        total_loss = model.loss(logits, y_placeholder)
        opt = optimizer(lr)
        gradients = opt.compute_gradients(total_loss, vars_.trainable_variables())
        gradients, variables = zip(*gradients)
        clipped_gradients, _ = clip_ops.clip_by_global_norm(gradients, 5.0)
        gradients = list(zip(clipped_gradients, variables))
        grad_updates = opt.apply_gradients(gradients, global_step=global_step, name="train")
        train_op = control_flow_ops.with_dependencies([grad_updates], total_loss)







        vidList = np.arange(totalVids)
        np.random.shuffle(vidList)
        numVids = 0
        acc=0
        for vid in vidList:
            input_data, label = load_data(model, vid, fName, '/z/home/madantrg/Datasets/HMDB51HDF5RGB/Split1',os.path.join('/z/home/erichof/TF_Activity_Recognition_Framework/datasets/HMDB51',fName+'01.txt'), '/z/home/erichof/TF_Activity_Recognition_Framework/datasets/HMDB51/classInd.txt', [224,224], False, 'HMDB51')
            labels = np.repeat(label, seqLength)
            _, loss_train, pred, gs = sess.run([train_op, total_loss, slogits, global_step], feed_dict={x_placeholder: input_data, y_placeholder: labels, j_placeholder: j_value})


            import pdb; pdb.set_trace()





















        import pdb; pdb.set_trace()
