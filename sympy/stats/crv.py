from rv import (Domain, SingleDomain, ConditionalDomain, ProductDomain, PSpace,
        random_symbols, ProductPSpace)
from sympy.functions.special.delta_functions import DiracDelta
from sympy import (S, Interval, Dummy, FiniteSet, Mul, Integral, And, Or,
        Piecewise, solve, cacheit)
from sympy.solvers.inequalities import reduce_poly_inequalities
from sympy import integrate as sympy_integrate
import random
oo = S.Infinity

def integrate(*args, **kwargs):
    """
    Wrap around sympy integrate function to include a evaluate flag
    if evaluate==False then just return the Integral object
    """
    evaluate = kwargs.get('evaluate', True)
    if evaluate:
        return sympy_integrate(*args)
    else:
        return Integral(*args)

class ContinuousDomain(Domain):
    """
    A domain with continuous support.
    Represented using symbols and Intervals
    """
    is_Continuous = True

    def as_boolean(self):
        raise NotImplementedError("Not Implemented for generic Domains")

class SingleContinuousDomain(ContinuousDomain, SingleDomain):
    def __new__(cls, symbol, set):
        assert symbol.is_Symbol
        symbols = FiniteSet(symbol)
        return Domain.__new__(cls, symbols, set)

    def integrate(self, expr, variables=None, **kwargs):
        if variables is None:
            variables = self.symbols
        if not variables:
            return expr
        assert frozenset(variables) == frozenset(self.symbols)
        # assumes only intervals
        return integrate(expr, (self.symbol, self.set), **kwargs)

    def as_boolean(self):
        return self.set.as_relational(self.symbol)


class ProductContinuousDomain(ProductDomain, ContinuousDomain):

    def integrate(self, expr, variables=None, **kwargs):
        if variables is None:
            variables = self.symbols
        for domain in self.domains:
            domain_vars = frozenset(variables) & frozenset(domain.symbols)
            if domain_vars:
                expr = domain.integrate(expr, domain_vars, **kwargs)
        return expr

    def as_boolean(self):
        return And(*[domain.as_boolean() for domain in self.domains])

class ConditionalContinuousDomain(ContinuousDomain, ConditionalDomain):

    def integrate(self, expr, variables=None, **kwargs):
        if variables is None:
            variables = self.symbols
        if not variables:
            return expr
        # Extract the full integral
        fullintgrl = self.fulldomain.integrate(expr, variables, evaluate=False)
        # separate into integrand and limits
        integrand, limits = fullintgrl.function, list(fullintgrl.limits)

        conditions = [self.condition]
        while conditions:
            cond = conditions.pop()
            if cond.is_Boolean:
                if cond.is_And:
                    conditions.extend(cond.args)
                elif cond.is_Or:
                    raise NotImplementedError("Or not implemented here")
            elif cond.is_Relational:
                if cond.is_Equality:
                    # Add the appropriate Delta to the integrand
                    integrand *= DiracDelta(cond.lhs-cond.rhs)
                else:
                    symbols = FiniteSet(cond.free_symbols) & self.symbols
                    if len(symbols)!=1: # Can't handle x > y
                        raise NotImplementedError(
                            "Multivariate Inequalities not yet implemented")
                    # Can handle x > 0
                    symbol = tuple(symbols)[0]
                    # Find the limit with x, such as (x, -oo, oo)
                    for i, limit in enumerate(limits):
                        if limit[0]==symbol:
                            # Make condition into an Interval like [0, oo]
                            cintvl = reduce_poly_inequalities_wrap(cond, symbol)
                            # Make limit into an Interval like [-oo, oo]
                            lintvl = Interval(limit[1], limit[2])
                            # Intersect them to get [0, oo]
                            intvl = cintvl.intersect(lintvl)
                            # Put back into limits list
                            limits[i] = (symbol, intvl.left, intvl.right)
            else:
                raise ValueError(
                        "Condition %s is not a relational or Boolean"%cond)

        return integrate(integrand, *limits, **kwargs)

    def as_boolean(self):
        return And(self.fulldomain.as_boolean(), self.condition)

    @property
    def set(self):
        if len(self.symbols) == 1:
            return (self.fulldomain.set & reduce_poly_inequalities_wrap(
                self.condition, tuple(self.symbols)[0]))
        else:
            raise NotImplementedError(
                    "Set of Conditional Domain not Implemented")

class ContinuousPSpace(PSpace):
    is_Continuous = True

    def integrate(self, expr, rvs=None, **kwargs):
        if rvs == None:
            rvs = self.values
        else:
            rvs = frozenset(rvs)

        expr = expr.subs(dict((rv, rv.symbol) for rv in rvs))

        domain_symbols = frozenset(rv.symbol for rv in rvs)

        return self.domain.integrate(self.density * expr,
                domain_symbols, **kwargs)

    def compute_density(self, expr, **kwargs):
        # Common case Density(X) where X in self.values
        if expr in self.values:
            # Marginalize all other random symbols out of the density
            density = self.domain.integrate(self.density, set(rs.symbol
                for rs in self.values - frozenset((expr,))),  **kwargs)
            return expr.symbol, density

        z = Dummy('z', real=True, finite=True)
        return z, self.integrate(DiracDelta(expr - z), **kwargs)

    def compute_cdf(self, expr, **kwargs):
        if not self.domain.set.is_Interval:
            raise ValueError("CDF not well defined on multivariate expressions")

        x,d = self.compute_density(expr, **kwargs)
        z = Dummy('z', real=True, finite=True)
        left_bound = self.domain.set.start

        # CDF is integral of PDF from left bound to z
        cdf = integrate(d, (x, left_bound, z), **kwargs)
        # CDF Ensure that CDF left of left_bound is zero
        cdf = Piecewise((0, z<left_bound), (cdf, True))
        return z, cdf

    def P(self, condition, **kwargs):
        # Univariate case can be handled by where
        try:
            domain = self.where(condition)
            rv = [rv for rv in self.values if rv.symbol == domain.symbol][0]
            # Integrate out all other random variables
            z, pdf = self.compute_density(rv, **kwargs)
            # Integrate out this last variable over the special domain
            return integrate(pdf, (z, domain.set), **kwargs)
        # Other cases can be turned into univariate case
        # by computing a density handled by density computation
        except NotImplementedError:
            expr = condition.lhs - condition.rhs
            val, density = self.compute_density(expr, **kwargs)
            # Turn problem into univariate case
            space = SingleContinuousPSpace(val, density)
            return space.P(condition.__class__(space.value, 0))


    def where(self, condition):
        rvs = frozenset(random_symbols(condition))
        if not (len(rvs)==1 and rvs.issubset(self.values)):
            raise NotImplementedError(
                    "Multiple continuous random variables not supported")
        rv = tuple(rvs)[0]
        interval = reduce_poly_inequalities_wrap(condition, rv)
        interval = interval.intersect(self.domain.set)
        return SingleContinuousDomain(rv.symbol, interval)

    def conditional_space(self, condition, normalize=True, **kwargs):

        condition = condition.subs(dict((rv,rv.symbol) for rv in self.values))

        domain = ConditionalContinuousDomain(self.domain, condition)
        density = self.density
        if normalize:
            density = density / domain.integrate(density, **kwargs)

        return ContinuousPSpace(domain, density)

class SingleContinuousPSpace(ContinuousPSpace):
    _count = 0
    _name = 'x'
    def __new__(cls, symbol, density, set=Interval(-oo, oo)):
        assert symbol.is_Symbol
        domain = SingleContinuousDomain(symbol, set)
        obj = ContinuousPSpace.__new__(cls, domain, density)
        obj._cdf = None
        return obj

    @property
    def value(self):
        return tuple(self.values)[0]

    @cacheit
    def _inverse_cdf_expression(self):
        """
        Inverse of the CDF

        See Also:
            compute_cdf
            sample
        """
        x,d = self.compute_cdf(self.value)
        z = Dummy('z', real=True, positive=True)
        # Invert CDF
        inverse_cdf = solve(d-z, x)
        if len(inverse_cdf) != 1:
            raise ValueError("Could not invert CDF")

        return z, inverse_cdf[0]

    def sample(self):
        """
        Internal sample method.
        Returns dictionary mapping RandomSymbol to realization value
        """
        z, icdf = self._inverse_cdf_expression()
        return {self.value: icdf.subs(z, random.uniform(0,1))}

class ProductContinuousPSpace(ProductPSpace, ContinuousPSpace):
    @property
    def density(self):
        return Mul(*[space.density for space in self.spaces])

def reduce_poly_inequalities_wrap(condition, var):
    if condition.is_Relational:
        return reduce_poly_inequalities([[condition]], var, relational=False)
    if condition.__class__ is Or:
        return reduce_poly_inequalities([list(condition.args)],
                var, relational=False)
    if condition.__class__ is And:
        intervals = [reduce_poly_inequalities([[arg]], var, relational=False)
            for arg in condition.args]
        I = intervals[0]
        for i in intervals:
            I = I.intersect(i)
        return I

