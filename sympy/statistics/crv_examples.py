from sympy import exp, sqrt, pi, S, Dummy, Interval, S, sympify, gamma
from crv import SingleContinuousPSpace, integrate
from sympy.core.decorators import _sympifyit

oo = S.Infinity

class NormalPSpace(SingleContinuousPSpace):
    def __new__(cls, mean, std, symbol = None):

        x = symbol or cls.create_symbol()
        pdf = exp(-(x-mean)**2 / (2*std**2)) / (sqrt(2*pi)*std)
        obj = SingleContinuousPSpace.__new__(cls, x, pdf)
        obj.mean = mean
        obj.std = std
        obj.variance = std**2
        return obj

def Normal(mean, std, symbol=None):
    return NormalPSpace(mean, std, symbol).value


class ExponentialPSpace(SingleContinuousPSpace):
    def __new__(cls, rate, symbol=None):
        x = symbol or cls.create_symbol()
        pdf = rate * exp(-rate*x)
        obj = SingleContinuousPSpace.__new__(cls, x, pdf, set = Interval(0, oo))
        obj.rate = rate
        return obj

def Exponential(rate, symbol=None):
    return ExponentialPSpace(rate, symbol).value

class ParetoPSpace(SingleContinuousPSpace):
    def __new__(cls, xm, alpha, symbol=None):
        assert xm>0, "Xm must be positive"
        assert alpha>0, "Alpha must be positive"

        x = symbol or cls.create_symbol()
        pdf = alpha * xm**alpha / x**(alpha+1)
        obj = SingleContinuousPSpace.__new__(cls, x, pdf, set=Interval(xm, oo))
        obj.xm = xm
        obj.alpha = alpha
        return obj

def Pareto(xm, alpha, symbol=None):
    return ParetoPSpace(xm, alpha, symbol).value


class BetaPSpace(SingleContinuousPSpace):
    def __new__(cls, alpha, beta, symbol=None):
        assert alpha>0, "Alpha must be positive"
        assert beta>0, "Beta must be positive"

        alpha, beta = sympify(alpha), sympify(beta)
        lazy = alpha.is_Symbol or beta.is_Symbol

        x = symbol or cls.create_symbol()
        pdf = x**(alpha-1) * (1-x)**(beta-1)
        pdf = pdf / integrate(pdf, (x, 0,1), lazy=lazy)

        obj = SingleContinuousPSpace.__new__(cls, x, pdf, set = Interval(0, 1))
        obj.alpha = alpha
        obj.beta = beta
        return obj

def Beta(alpha, beta, symbol=None):
    return BetaPSpace(alpha, beta, symbol).value

class GammaPSpace(SingleContinuousPSpace):
    def __new__(cls, k, theta, symbol=None):
        assert k>0, "k must be positive"
        assert theta>0, "theta must be positive"

        x = symbol or cls.create_symbol()
        pdf = x**(k-1) * exp(-x/theta) / (gamma(k)*theta**k)

        obj = SingleContinuousPSpace.__new__(cls, x, pdf, set = Interval(0, oo))
        obj.k = k
        obj.theta = theta
        return obj

def Gamma(k, theta, symbol=None):
    return GammaPSpace(k, theta, symbol).value
