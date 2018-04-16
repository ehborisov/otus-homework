import numpy as np
import math
from scipy import sparse


class LogisticRegression:
    def __init__(self):
        self.w = None
        self.loss_history = None

    def train(self, X, y, learning_rate=1e-3, reg=1e-5, num_iters=100,
              batch_size=200, verbose=False):
        """
        Train this classifier using stochastic gradient descent.

        Inputs:
        - X: N x D array of training data. Each training point is a D-dimensional
             column.
        - y: 1-dimensional array of length N with labels 0-1, for 2 classes.
        - learning_rate: (float) learning rate for optimization.
        - reg: (float) regularization strength.
        - num_iters: (integer) number of steps to take when optimizing
        - batch_size: (integer) number of training examples to use at each step.
        - verbose: (boolean) If true, print progress during optimization.

        Outputs:
        A list containing the value of the loss function at each training iteration.
        """
        # Add a column of ones to X for the bias sake.
        X = LogisticRegression.append_biases(X)
        num_train, dim = X.shape
        if self.w is None:
            # lazily initialize weights
            self.w = np.random.randn(dim) * 0.01

        # Run stochastic gradient descent to optimize W
        self.loss_history = []
        for it in range(num_iters):
            sample_indices = np.random.choice(X.shape[0], batch_size, True)
            X_batch = X[sample_indices, :]
            y_batch = [y[i] for i in sample_indices]
            # evaluate loss and gradient
            loss, grad = self.loss(X_batch, y_batch, reg)
            self.loss_history.append(loss)
            self.w = self.w - learning_rate*grad

            if verbose and it % 100 == 0:
                print('iteration %d / %d: loss %f' % (it, num_iters, loss))

        return self

    def predict_proba(self, X, append_bias=False):
        """
        Use the trained weights of this linear classifier to predict probabilities for
        data points.

        Inputs:
        - X: N x D array of data. Each row is a D-dimensional point.
        - append_bias: bool. Whether to append bias before predicting or not.

        Returns:
        - y_proba: Probabilities of classes for the data in X. y_pred is a 2-dimensional
          array with a shape (N, 2), and each row is a distribution of classes [prob_class_0, prob_class_1].
        """
        if append_bias:
            X = LogisticRegression.append_biases(X)
        dotp = -X.dot(self.w)
        sig = np.vectorize(lambda x: 1 / (1 + math.exp(x)))
        p_1 = sig(dotp)
        p_0 = np.subtract(1, p_1)
        return np.transpose(np.vstack((p_0, p_1)))

    def predict(self, X):
        """
        Use the ```predict_proba``` method to predict labels for data points.

        Inputs:
        - X: N x D array of training data. Each column is a D-dimensional point.

        Returns:
        - y_pred: Predicted labels for the data in X. y_pred is a 1-dimensional
          array of length N, and each element is an integer giving the predicted
          class.
        """

        y_proba = self.predict_proba(X, append_bias=True)
        return np.greater(y_proba[:, 0], y_proba[:, 1]).astype(int)

    def loss(self, X_batch, y_batch, reg):
        """Logistic Regression loss function
        Inputs:
        - X: N x D array of data. Data are D-dimensional rows
        - y: 1-dimensional array of length N with labels 0-1, for 2 classes
        - reg: (float) regularization strength.
        Returns:
        a tuple of:
        - loss as single float
        - gradient with respect to weights w; an array of same shape as w
        """
        dotp = -X_batch.dot(self.w)
        odds = 1 / (1 + np.exp(dotp))
        y_batch = np.array(y_batch)
        loss = - np.sum(y_batch * np.log(odds) + (1 - y_batch) * np.log(1 - odds))
        dw = X_batch.T.dot(odds - y_batch)

        sample_size = X_batch.shape[0]
        avg_loss = loss/sample_size + (reg/2*sample_size)*(self.w[:-1].dot(self.w[:-1]))
        reg = (reg/sample_size * self.w[:-1])
        reg = np.append(reg, 0)  # exclude bias term
        avg_grad = dw / sample_size + reg
        return avg_loss, avg_grad

    @staticmethod
    def append_biases(X):
        return sparse.hstack((X, np.ones(X.shape[0])[:, np.newaxis])).tocsr()
