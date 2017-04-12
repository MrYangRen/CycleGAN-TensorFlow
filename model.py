import tensorflow as tf
import ops
import utils
from discriminator import Discriminator
from generator import Generator

class CycleGAN:
  def __init__(self, lambda1=10, lambda2=10, use_lsgan=True):
    """
    Args:
      lambda1: integer, forward cycle loss weight
      lambda2: integer, backward cycle loss weight
      use_lsgan: boolean
    """
    self.lambda1 = lambda1
    self.lambda2 = lambda2
    self.use_lsgan = use_lsgan
    use_sigmoid = not use_lsgan

    self.G = Generator('G')
    self.D_Y = Discriminator('D_Y', use_sigmoid=use_sigmoid)
    self.F = Generator('F')
    self.D_X = Discriminator('D_X', use_sigmoid=use_sigmoid)

  def discriminator_loss(self, G, D, x, y, use_lsgan=True):
    """ note: D(y).shape == (batch_size,8,8,1)
    """
    if use_lsgan:
      # use mean squared error
      error_real = tf.reduce_mean(tf.squared_difference(D(y),1))
      error_fake = tf.reduce_mean(tf.square(D(G(x))))
    else:
      # use cross entropy
      error_real = -tf.reduce_mean(ops.safe_log(D(y)))
      error_fake = -tf.reduce_mean(ops.safe_log(1-D(G(x))))
    loss = (error_real + error_fake) / 2
    return loss

  def generator_loss(self, G, D, x, use_lsgan=True):
    """ try to fool discriminator into believing that G(x) is real
    """
    if use_lsgan:
      # use mean squared error
      loss = tf.reduce_mean(tf.squared_difference(D(G(x)),1))
    else:
      # heuristic, non-saturating loss
      loss = -tf.reduce_mean(ops.safe_log(D(G(x)))) / 2
    return loss

  def cycle_consistency_loss(self, G, F, x, y):
    """ cycle consistency loss (L1 norm)
    """
    forward_loss = tf.reduce_mean(tf.abs(F(G(x))-x))
    backward_loss = tf.reduce_mean(tf.abs(G(F(y))-y))
    loss = self.lambda1*forward_loss + self.lambda2*backward_loss
    return loss

  def model(self, x, y):
    cycle_loss = self.cycle_consistency_loss(self.G, self.F, x, y)

    # X -> Y
    G_gan_loss = self.generator_loss(self.G, self.D_Y, x, use_lsgan=self.use_lsgan)
    G_loss =  G_gan_loss + cycle_loss
    D_Y_loss = self.discriminator_loss(self.G, self.D_Y, x, y, use_lsgan=self.use_lsgan)

    tf.summary.histogram('D_Y/true', self.D_Y(y))
    tf.summary.histogram('D_Y/fake', self.D_Y(self.G(x)))

    # Y -> X
    F_gan_loss = self.generator_loss(self.F, self.D_X, y, use_lsgan=self.use_lsgan)
    F_loss = F_gan_loss + cycle_loss
    D_X_loss = self.discriminator_loss(self.F, self.D_X, y, x, use_lsgan=self.use_lsgan)

    # summary
    tf.summary.histogram('D_X/true', self.D_X(x))
    tf.summary.histogram('D_X/fake', self.D_X(self.F(y)))

    tf.summary.scalar('loss/G', G_gan_loss)
    tf.summary.scalar('loss/D_Y', D_Y_loss)
    tf.summary.scalar('loss/F', F_gan_loss)
    tf.summary.scalar('loss/D_X', D_X_loss)
    tf.summary.scalar('loss/cycle', cycle_loss)

    tf.summary.image('X/generated', utils.convert2int(self.G(x)))
    tf.summary.image('X/reconstruction', utils.convert2int(self.F(self.G(x))))
    tf.summary.image('Y/generated', utils.convert2int(self.F(y)))
    tf.summary.image('Y/reconstruction', utils.convert2int(self.G(self.F(y))))

    summary_op = tf.summary.merge_all()

    return G_loss, D_Y_loss, F_loss, D_X_loss, summary_op

  def optimize(self, G_loss, D_Y_loss, F_loss, D_X_loss):
    optimizer = tf.train.AdamOptimizer(learning_rate=2e-4)

    G_minimizer = optimizer.minimize(G_loss, var_list=self.G.variables)
    D_Y_minimizer = optimizer.minimize(D_Y_loss, var_list=self.D_Y.variables)
    F_minimizer = optimizer.minimize(F_loss, var_list=self.F.variables)
    D_X_minimizer = optimizer.minimize(D_X_loss, var_list=self.D_X.variables)

    with tf.control_dependencies([G_minimizer, D_Y_minimizer, F_minimizer, D_X_minimizer]):
      return tf.no_op(name='train')