import tensorflow as tf
import numpy as np
import malis

class MalisWeights(object):

    def __init__(self, output_shape, neighborhood):

        self.output_shape = np.asarray(output_shape)
        self.neighborhood = np.asarray(neighborhood)
        self.edge_list = malis.nodelist_like(self.output_shape, self.neighborhood)

    def get_edge_weights(self, affs, gt_affs, gt_seg):

        assert affs.shape[0] == len(self.neighborhood)

        weights_neg = self.malis_pass(affs, gt_seg, pos=0)
        weights_pos = self.malis_pass(affs, gt_seg, pos=1)

        # positive samples don't contribute in the negative pass
        weights_neg[gt_affs==1] = 0
        weights_neg = weights_neg/np.sum(weights_neg)

        # negative samples don't contribute in the positive pass
        weights_pos[gt_affs==0] = 0
        weights_pos = weights_pos/np.sum(weights_pos)

        weights = weights_neg + weights_pos

        return weights

    def malis_pass(self, affs, gt_seg, pos):

        weights = malis.malis_loss_weights(
            gt_seg.astype(np.uint64).flatten(),
            self.edge_list[0].flatten(),
            self.edge_list[1].flatten(),
            affs.astype(np.float32).flatten(),
            pos)

        weights = weights.reshape((-1,) + tuple(self.output_shape))
        assert weights.shape[0] == len(self.neighborhood)

        return weights.astype(np.float32)

def malis_weights_op(affs, gt_affs, gt_seg, neighborhood, name=None):
    '''Returns a tensorflow op to compute the weights of the MALIS loss. This
    is to be multiplied with an edge-wise loss (e.g., an Euclidean loss).
    '''

    output_shape = gt_seg.get_shape().as_list()

    malis_weights = MalisWeights(output_shape, neighborhood)
    malis_functor = lambda affs, gt_affs, gt_seg, mw=malis_weights: \
        mw.get_edge_weights(affs, gt_affs, gt_seg)

    weights = tf.py_func(
        malis_functor,
        [affs, gt_affs, gt_seg],
        [tf.float32],
        name=name)

    return weights[0]

def malis_loss_op(affs, gt_affs, gt_seg, neighborhood, name=None):
    '''Returns a tensorflow op to compute the MALIS loss.'''

    weights = malis_weights_op(affs, gt_affs, gt_seg, neighborhood, name)
    edge_loss = tf.square(tf.subtract(gt_affs, affs))

    return tf.reduce_sum(tf.multiply(weights, edge_loss))
