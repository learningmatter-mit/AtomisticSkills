import numpy as np
from sklearn.linear_model import *
from sklearn.metrics import r2_score
from sklearn.metrics import mean_squared_error

__author__ = "Julia Yang"
__date__ = '2022/05/04'


def make_groups(sw, ignore=1):
    groups = []
    # ignore tells us to ignore the point terms as they have been regressed on already
    group_id = 1  # start by grouping the pairs together

    # groups all bit combos together
    for orbit_size in sw.cluster_subspace.orbits_by_size:
        if orbit_size == ignore: continue
        for orbit in sw.cluster_subspace.orbits_by_size[orbit_size]:
            group_id += 1
            for _ in orbit.bit_combos:
                groups.append(group_id)
    return groups


def zero_coefficients(beta, cutoff=1E-5):
    to_prune = []
    new_beta = []
    for i_coef in range(len(beta)):
        if np.abs(beta[i_coef]) <= cutoff:
            to_prune.append(i_coef)
            new_beta.append(0.0)
        else:
            new_beta.append(beta[i_coef])
    return to_prune


class SparseGroupLasso(object):
    def __init__(self, groups, lambd, alpha=None, intercept=None):
        """
        Compress features using sparse group lasso in an iterative fashion (instead of cyclically, as is done in
        the Sparse Group Lasso paper by Simon, Friedman, Hastie, and Tishirani (2011).

        :param groups: numpy array with length equal to no. of basis functions, and grouped by orbit number.
        :param lambd: amount of L1 mixing
        :param alpha: penalty applied to both L1 and L2
        :param intercept: Pass in existing intercept
        """
        self.groups = groups
        self.lambd = lambd  # amount of L1 to mix in
        self.alpha = alpha
        self.intercept = intercept
        self.coef_ = None

    def set_params(self, alpha):
        self.alpha = alpha

    def do_soft_thresholding_operator(self, z, alphaLambd):
        return np.sign(z) * (np.abs(z) - alphaLambd)

    def fit(self, X, Y, ):
        # same thing as evaluate
        assert X.shape[1] == len(self.groups)
        self.X = X
        self.Y = Y
        loss_function = 0
        intercept = 0.
        all_coef = []
        alpha = self.alpha
        cutoff = alpha * (1 - self.lambd)
        Yprime = self.Y
        for iGroup in range(min(self.groups), max(self.groups) + 1):
            l = np.where(self.groups == iGroup)[0]
            S = self.do_soft_thresholding_operator(
                np.dot(self.X[:, l].T, Yprime) / len(Yprime),
                self.lambd * alpha)
            if np.linalg.norm(S, ord=2) < cutoff * len(l) ** 0.5:  # SGL paper cutoff
                coef = np.zeros(len(l))
                l1 = 0  # zero out contribution to objective function
                l2 = 0  # zero out contribution to objective function
            else:
                # do the fitting with group k
                fitElastic = ElasticNet(fit_intercept=False, alpha=alpha, selection='random',
                                        l1_ratio=self.lambd).fit(self.X[:, l],
                                                                 Yprime)
                l1 = alpha * (self.lambd) * \
                     np.linalg.norm(fitElastic.coef_, ord=1)
                l2 = alpha * (1 - self.lambd) * \
                     np.linalg.norm(fitElastic.coef_, ord=2) * np.sqrt(len(l))
                coef = fitElastic.coef_
            # determine if coefficients should be 0, step 2 in 3.2 of SGL paper

            loss_function += (l1 + l2)
            all_coef.extend(coef)
            coef = coef.reshape(-1, 1)  # added this 2021/04/29
            Yprime -= np.dot(self.X[:, l], coef)  # have to subtract all other group fits
            # intercept += fit.intercept_
        self.coef_ = np.array(all_coef)
        self.intercept = intercept

        return self

    def predict(self, X):
        return np.dot(X, self.coef_.T)

    def evaluate(self, X, Y):
        assert X.shape[1] == len(self.groups)
        self.X = X
        self.Y = Y
        loss_function = 0
        intercept = 0.
        all_coef = []
        alpha = self.alpha
        cutoff = alpha * (1 - self.lambd)
        Yprime = self.Y
        for iGroup in range(min(self.groups), max(self.groups) + 1):
            l = np.where(self.groups == iGroup)[0]
            S = self.do_soft_thresholding_operator(
                np.dot(self.X[:, l].T, Yprime) / len(Yprime),
                self.lambd * alpha)
            if np.linalg.norm(S, ord=2) < cutoff * len(l) ** 0.5:  # SGL paper cutoff
                coef = np.zeros(len(l))
                l1 = 0  # l1 zeroed out the
                l2 = 0  # zero out the group
            else:
                # do the fitting with group k
                fitElastic = ElasticNet(fit_intercept=False, alpha=alpha, selection='random',
                                        l1_ratio=self.lambd).fit(self.X[:, l],
                                                                 Yprime)
                l1 = alpha * (self.lambd) * \
                     np.linalg.norm(fitElastic.coef_, ord=1)
                l2 = alpha * (1 - self.lambd) * \
                     np.linalg.norm(fitElastic.coef_, ord=2) * np.sqrt(len(l))
                coef = fitElastic.coef_
            # determine if coefficients should be 0, step 2 in 3.2 of SGL paper

            loss_function += (l1 + l2)
            all_coef.extend(coef)
            coef = coef.reshape(-1, 1)  # added this 2021/04/29
            Yprime -= np.dot(self.X[:, l], coef)  # have to subtract all other group fits
            # intercept += fit.intercept_
        self.coef_ = np.array(all_coef)
        self.intercept = intercept

        return loss_function + 1 / (2 * len(self.Y)) * \
               np.linalg.norm(self.Y - np.dot(self.X, self.coef_),
                              ord=2) ** 2

    def score(self, X, Y):
        y_pred = self.predict(X).T
        return np.sqrt(mean_squared_error(Y, y_pred))

    def get_params(self, deep=False):
        return {'groups': self.groups,
                'coef_': self.coef_,
                'lambd': self.lambd,
                'alpha': self.alpha,
                'intercept': self.intercept}