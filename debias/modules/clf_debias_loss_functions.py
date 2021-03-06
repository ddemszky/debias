import tensorflow as tf

from debias.utils import ops
from debias.utils.configured import Configured


class ClfDebiasLossFunction(Configured):
  """Classification debiasing loss functions."""

  def compute_clf_loss(self, hidden, logits, bias, labels):
    """
    :param hidden: [batch, n_hidden] hidden units from the model
    :param logits: [batch, n_classes] per-class logit scores
    :param bias: [batch, n_classes] per-class log-probabilities from the bias
    :param labels: [batch] labels
    :return: scalar loss
    """
    raise NotImplementedError()


class Plain(ClfDebiasLossFunction):
  def compute_clf_loss(self, hidden, logits, bias, labels, mask=None):
    loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=labels)
    return tf.reduce_mean(loss)


class Reweight(ClfDebiasLossFunction):
  def compute_clf_loss(self, hidden, logits, bias, labels, mask=None):
    loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=labels)
    label_one_hot = tf.one_hot(labels, ops.get_shape_tuple(logits, 1))
    weights = 1 - tf.reduce_sum(tf.exp(bias) * label_one_hot, 1)
    return tf.reduce_sum(weights*loss) / tf.reduce_sum(weights)


class BiasProduct(ClfDebiasLossFunction):
  def compute_clf_loss(self, hidden, logits, bias, labels):
    logits = tf.nn.log_softmax(logits)
    loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits+bias, labels=labels)
    return tf.reduce_mean(loss)


class LearnedMixin(ClfDebiasLossFunction):
  def __init__(self, w):
    self.w = w

  def compute_clf_loss(self, hidden, logits, bias, labels):
    logits = tf.nn.log_softmax(logits)

    factor = tf.get_variable("factor-b", ())
    factor += ops.last_dim_weighted_sum(hidden, "scale-w")
    factor = tf.nn.softplus(factor)
    bias *= tf.expand_dims(factor, 1)

    loss = tf.nn.sparse_softmax_cross_entropy_with_logits(
      logits=logits+bias, labels=labels)
    loss = tf.reduce_mean(loss)

    if self.w == 0:
      return loss

    loss += self.w * ops.entropy(bias)
    return loss

  def __setstate__(self, state):
    # TODO remove
    if "normalize_bias" in state:
      del state["normalize_bias"]
    super().__setstate__(state)
