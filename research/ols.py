"""Minimal OLS with Newey-West (HAC) standard errors.

statsmodels would do this in one line, but hand-rolling it keeps the GitHub
Action's dependency set to numpy/scipy/pandas/requests, which is the whole
install budget for a job that runs weekly on a free runner.

Newey-West rather than plain OLS SEs because monthly conflict intensity is
strongly autocorrelated; classical SEs would be optimistically small and the
|t| > 2 gate is the one thing in this project that must not be too generous.
"""

import numpy as np
from scipy import stats


class OLSResult:
    def __init__(self, names, beta, se, tstat, pvalue, r2, adj_r2, nobs):
        self.names = names
        self.beta = beta
        self.se = se
        self.tstat = tstat
        self.pvalue = pvalue
        self.r2 = r2
        self.adj_r2 = adj_r2
        self.nobs = nobs

    def get(self, name):
        i = self.names.index(name)
        return {
            "beta": float(self.beta[i]),
            "se": float(self.se[i]),
            "tstat": float(self.tstat[i]),
            "pvalue": float(self.pvalue[i]),
        }

    def __repr__(self):
        rows = [f"n={self.nobs} r2={self.r2:.4f} adj_r2={self.adj_r2:.4f}"]
        for i, nm in enumerate(self.names):
            rows.append(
                f"  {nm:<22} beta={self.beta[i]: .6f} "
                f"se={self.se[i]:.6f} t={self.tstat[i]: .3f} p={self.pvalue[i]:.4f}"
            )
        return "\n".join(rows)


def _newey_west_lags(n):
    """Standard Bartlett bandwidth rule: floor(4 * (n/100)^(2/9))."""
    return max(1, int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def ols_hac(y, X, names, lags=None, add_const=True):
    """Regress y on X with Newey-West HAC standard errors.

    y     : (n,) array of outcomes
    X     : (n, k) array of regressors, WITHOUT a constant column
    names : list of k regressor names
    """
    y = np.asarray(y, dtype=float).ravel()
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.shape[0] != y.shape[0]:
        X = X.T
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"shape mismatch: y={y.shape} X={X.shape}")

    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    y, X = y[ok], X[ok]

    full_names = list(names)
    if add_const:
        X = np.column_stack([np.ones(len(y)), X])
        full_names = ["const"] + full_names

    n, k = X.shape
    if n <= k + 2:
        raise ValueError(f"not enough observations: n={n}, k={k}")

    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta

    if lags is None:
        lags = _newey_west_lags(n)

    # S = sum_j w_j * (Gamma_j + Gamma_j')  with Bartlett weights
    u = X * resid[:, None]
    S = u.T @ u
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)
        G = u[lag:].T @ u[:-lag]
        S += w * (G + G.T)

    cov = XtX_inv @ S @ XtX_inv
    # Small-sample correction, matching statsmodels' default HAC behaviour.
    cov *= n / float(n - k)

    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = np.where(se > 0, beta / se, 0.0)
    pvalue = 2.0 * (1.0 - stats.t.cdf(np.abs(tstat), df=n - k))

    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / float(n - k) if n > k else 0.0

    return OLSResult(full_names, beta, se, tstat, pvalue, r2, adj_r2, n)
