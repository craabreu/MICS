"""
.. module:: mixtures
   :platform: Unix, Windows
   :synopsis: a module for defining the class :class:`Mixture`.

.. moduleauthor:: Charlles R. A. Abreu <abreu@eq.ufrj.br>


"""

import numpy as np
from numpy.linalg import multi_dot

from mics.mixtures import mixture
from mics.utils import covariance
from mics.utils import cross_covariance
from mics.utils import info
from mics.utils import pinv


class MICS(mixture):
    """A mixture of independently collected samples (MICS)

        Args:
            samples (list or tuple):
                a list of samples.
            title (str, optional):
                a title.
            verbose (bool, optional):
                a verbosity tag.
            tol (float, optional):
                a tolerance.

    """

    # ======================================================================================
    def __init__(self, samples, title="Untitled", verbose=False, tol=1.0E-12):

        m, n, neff = self.__define__(samples, title, verbose)

        b = self.b = [s.b for s in samples]
        pi = self.pi = neff/sum(neff)
        verbose and info("Mixture composition:", pi)

        P = self.P = [np.empty([m, k], np.float64) for k in self.n]
        pm = self.pm = [np.empty(m, np.float64) for k in self.n]
        self.u0 = [np.empty([1, k], np.float64) for k in self.n]

        verbose and info("Solving self-consistent equations...")
        iter = 1
        df = self._newton_raphson_iteration()
        verbose and info("Maximum deviation at iteration %d:" % iter, max(abs(df)))
        while any(abs(df) > tol):
            iter += 1
            self.f[1:m] += df
            df = self._newton_raphson_iteration()
            verbose and info("Maximum deviation at iteration %d:" % iter, max(abs(df)))
        verbose and info("Free energies after convergence:", self.f)

        self.Sp0 = sum(pi[i]**2*covariance(P[i], pm[i], b[i]) for i in range(m))
        self.Theta = multi_dot([self.iB0, self.Sp0, self.iB0])
        verbose and info("Free-energy covariance matrix:", self.Theta)

        self.Overlap = np.stack(pm)
        verbose and info("Overlap matrix:", self.Overlap)

    # ======================================================================================
    def _newton_raphson_iteration(self):
        m = self.m
        u = self.u
        P = self.P
        pi = self.pi
        g = (self.f + np.log(pi))[:, np.newaxis]
        S = range(m)
        for i in S:
            x = g - u[i]
            xmax = np.amax(x, axis=0)
            numer = np.exp(x - xmax)
            denom = np.sum(numer, axis=0)
            self.P[i] = numer / denom
            self.u0[i] = -(xmax + np.log(denom))
            self.pm[i] = np.mean(P[i], axis=1)

        p0 = self.p0 = sum(pi[i]*self.pm[i] for i in S)
        B0 = np.diag(p0) - sum(pi[i]*np.matmul(P[i], P[i].T)/self.n[i] for i in S)
        self.iB0 = pinv(B0)
        df = np.matmul(self.iB0, pi - p0)
        return df[1:m] - df[0]

    # ======================================================================================
    def __reweight__(self, u, y, ref=0):
        S = range(self.m)
        pi = self.pi
        P = self.P
        pm = self.pm
        b = self.b

        w = [np.exp(self.u0[i] - u[i]) for i in S]
        z = [w[i]*y[i] for i in S]

        iw0 = 1.0/sum(pi[i]*np.mean(w[i], axis=1) for i in S)[0]
        yu = sum(pi[i]*np.mean(z[i], axis=1) for i in S)*iw0
        fu = np.array([np.log(iw0) - self.f[ref]])

        r = [np.concatenate((z[i], w[i])) for i in S]
        rm = [np.mean(r[i], axis=1) for i in S]
        Sp0r0 = sum(pi[i]**2*cross_covariance(P[i], pm[i], r[i], rm[i], b[i]) for i in S)
        Sr0 = sum(pi[i]**2*covariance(r[i], rm[i], b[i]) for i in S)
        Ss0 = np.block([[self.Sp0, Sp0r0], [Sp0r0.T, Sr0]])

        pu = sum(pi[i]*np.mean(w[i]*P[i], axis=1) for i in S)*iw0
        pytu = sum(pi[i]*np.matmul(P[i], z[i].T)/self.n[i] for i in S)*iw0

        Dyup0 = np.matmul(self.iB0, np.outer(pu, yu) - pytu)
        Dyuz0 = np.diag(np.repeat(iw0, len(yu)))
        Dyuw0 = -yu[np.newaxis, :]*iw0

        pu[ref] -= 1.0
        Dfup0 = np.matmul(self.iB0, pu[:, np.newaxis])
        Dfuz0 = np.zeros([len(yu), 1])
        Dfuw0 = iw0

        G = np.block([[Dfup0, Dyup0],
                      [Dfuz0, Dyuz0],
                      [Dfuw0, Dyuw0]])

        Theta = multi_dot([G.T, Ss0, G])

        return np.concatenate([fu, yu]), Theta

    # ======================================================================================
    def __perturb__(self, u, ref=0):
        S = range(self.m)
        pi = self.pi
        P = self.P
        pm = self.pm
        b = self.b

        w = [np.exp(self.u0[i] - u[i]) for i in S]
        iw0 = 1.0/sum(pi[i]*np.mean(w[i], axis=1) for i in S)[0]

        wm = [np.mean(w[i], axis=1) for i in S]
        Sp0w0 = sum(pi[i]**2*cross_covariance(P[i], pm[i], w[i], wm[i], b[i]) for i in S)
        Sw0 = sum(pi[i]**2*covariance(w[i], wm[i], b[i]) for i in S)
        Ss0 = np.block([[self.Sp0, Sp0w0], [Sp0w0.T, Sw0]])

        pu = sum(pi[i]*np.mean(w[i]*P[i], axis=1) for i in S)*iw0
        pu[ref] -= 1.0
        G = np.append(np.matmul(self.iB0, pu[:, np.newaxis]), iw0)

        f = np.log(iw0) - self.f[ref]
        df = np.sqrt(multi_dot([G.T, Ss0, G]))

        return f, df
