from abc import ABCMeta, abstractmethod
import random
import math
import sys

class ParamDef(object):
    """
    This represents the base class for a parameter definition.

    Every member of this class has to implement at least the
    is_in_parameter_domain method to check whether objects are in the parameter
    domain.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def is_in_parameter_domain(self, value):
        """
        Should test whether a certain value is in the parameter domain as
        defined by this class.

        Note that you have to test a value that is not warped in here. A
        warped-in value can be tested by checking whether it is in [0, 1].

        Parameters
        ----------
        value : object
            Tests whether the object is in the parameter domain.

        Returns
        -------
        is_in_parameter_domain : bool
            True iff value is in the parameter domain as defined by this
            instance.
        """
        pass

    def distance(self, valueA, valueB):
        """
        Returns the distance between `valueA` and `valueB`.
        In this case, it's 0 iff valueA == valueB, 1 otherwise.
        """
        if valueA == valueB:
            return 0
        return 1

    def to_dict(self):
        """
        This returns a dictionary from which we can build a new instance of
        the parameter.

        Returns
        -------
        dict : dictionary
            The dictionary from which we can rebuild this parameter definition.
        """
        result_dict = self.__dict__
        result_dict["type"] = self.__class__.__name__
        return result_dict

    @abstractmethod
    def warp_in(self, unwarped_value):
        """
        Warps value_in into a [0, 1] hypercube represented by a list.

        Parameters
        ----------
        unwarped_value :
            The value to be warped in. Has to be in parameter domain of this
            class.

        Returns
        -------
        warped_value : list of floats in [0, 1]
            The warped value. Length of the list is equal to the return of
            warped_size()
        """
        pass

    @abstractmethod
    def warp_out(self, warped_value):
        """
        Warps a [0, 1] hypercube position representing a value to said value.

        Parameters
        ----------
        warped_value : list of floats in [0, 1]
            The warped value. Length of the list is equal to the return of
            warped_size()

        Returns
        -------
        unwarped_value :
            The value to be warped in. Has to be in parameter domain of this
            class.
        """
        pass

    @abstractmethod
    def warped_size(self):
        """
        Returns the size a list of this parameters' warped values will have.
        """
        pass


class ComparableParamDef(object):
    """
    This class defines an ordinal parameter definition subclass, that is a
     parameter definition in which the values are comparable.
    It additionally implements the compare_values_function.
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        pass

    @abstractmethod
    def compare_values(self, one, two):
        """
        Compare values one and two of this datatype.

        It has to follow the same return semantics as the Python standard
        __cmp__ methods, meaning it returns negative integer if one < two,
        zero if one == two, a positive integer if one > two.

        Parameters
        ----------
        one : object in parameter definition
            The first value used in comparison.

        two : object in parameter definition
            The second value used in comparison.

        Returns
        -------
        comp: integer
            comp < 0 iff one < two.
            comp = 0 iff one = two.
            comp > 0 iff one > two.
        """
        pass



class NominalParamDef(ParamDef):
    """
    This defines a nominal parameter definition.

    A nominal parameter definition is defined by the values as given in the
    init function. These are a list of possible values it can take.
    """
    values = None

    def __init__(self, values):
        """
        Instantiates the NominalParamDef instance.

        Parameters
        ----------
        values : list
            A list of values which are the possible values that are in this
            parameter definition.

        Raises
        ------
        ValueError :
            Iff values is not a list, or values is an empty list.
        """
        if not isinstance(values, list):
            raise ValueError(
                "You created a NominalParameterDef object without "
                "specifying the possible values list.")

        if len(values) < 1:
            raise ValueError(
                "You need to specify a list of all possible values for this "
                "data type in order to make it being used for your "
                "optimization! The given list was empty: " + str(values)
            )

        self.values = values

    def is_in_parameter_domain(self, value):
        """
        Tests whether value is in self.values as defined during the init
        function.
        """
        return value in self.values

    def warp_in(self, unwarped_value):
        warped_value = [0]*len(self.values)
        warped_value[self.values.index(unwarped_value)] = 1
        return warped_value

    def warp_out(self, warped_value):
        warped_value = list(warped_value)
        return self.values[warped_value.index(max(warped_value))]

    def warped_size(self):
        return len(self.values)


class OrdinalParamDef(NominalParamDef, ComparableParamDef):
    """
    Defines an ordinal parameter definition.

    This class inherits from NominalParamDef and ComparableParameterDef, and
    consists of basically a list of possible values with a defined order. This
    defined order is simply the order in which the elements are in the list.
    """
    def __init__(self, values):
        super(OrdinalParamDef, self).__init__(values)

    def compare_values(self, one, two):
        """
        Compare values of this ordinal data type. Return is the same
        semantic as in __cmp__.

        Comparison takes place based on the index the given values one and
        two have in the values list in this object. Meaning if this ordinal
        parameter definition has a values list of [3,5,1,4]', then '5' will be
        considered smaller than '1' and '1' bigger than '5' because the index
        of '1' in this list is higher than the index of '5'.
        """
        if one not in self.values or two not in self.values:
            raise ValueError(
                "Values not comparable! Either one or the other is not in the "
                "values domain")

        if self.values.index(one) < self.values.index(two):
            return -1
        if self.values.index(one) > self.values.index(two):
            return 1

        return 0

    def distance(self, valueA, valueB):
        """
        This distance is defined as the absolute difference between the values'
        position in the list, normed to the [0, 1] hypercube.
        """
        if valueA not in self.values or valueB not in self.values:
            raise ValueError(
                "Values not comparable! Either one or the other is not in the "
                "values domain")
        indexA = self.values.index(valueA)
        indexB = self.values.index(valueB)
        diff = abs(indexA - indexB)
        return float(diff)/len(self.values)


class NumericParamDef(ParamDef, ComparableParamDef):
    """
    This class defines a numeric parameter definition.

    It is characterized through the existence of a warp_in and a warp_out
    function. The warp_in function squishes the whole parameter space to the
    unit space [0, 1], while the warp_out function reverses this.
    Note that it is necessary that
        x = warp_in(warp_out(x)) for x in [0, 1] and
        x = warp_out(warp_in(x)) for x in allowed parameter space.
    """
    warping_in = None
    warping_out = None

    def __init__(self, warping_in, warping_out):
        """
        Initializes the Numeric Param Def.

        Parameters
        ----------
        warping_in : function
            warping_in must take a value and return a corresponding value in
            the [0, 1] space.
        warping_out : function
            warping_out is the reverse function to warping_in.
        """
        super(NumericParamDef, self).__init__()
        self.warping_in = warping_in
        self.warping_out = warping_out

    def is_in_parameter_domain(self, value):
        """
        Uses the warp_out function for tests.
        """
        if 0 <= self.warp_in(value)[0] <= 1:
            return True
        return False

    def warp_in(self, unwarped_value):
        return [self.warping_in(unwarped_value)]

    def warp_out(self, warped_value):
        return self.warping_out(warped_value[0])

    def warped_size(self):
        return 1

    def compare_values(self, one, two):
        if not self.is_in_parameter_domain(one):
            raise ValueError("Parameter one = " + str(one) + " not in value "
                "domain.")
        if not self.is_in_parameter_domain(two):
            raise ValueError("Parameter two = " + str(two) + " not in value "
                "domain.")
        if one < two:
            return -1
        elif one > two:
            return 1
        else:
            return 0

    def distance(self, valueA, valueB):
        if not self.is_in_parameter_domain(valueA):
            raise ValueError("Parameter one = " + str(valueA) + " not in value "
                "domain.")
        if not self.is_in_parameter_domain(valueB):
            raise ValueError("Parameter two = " + str(valueB) + " not in value "
                "domain.")
        return self.warp_in(valueB)[0] - self.warp_in(valueA)[0]


class MinMaxNumericParamDef(NumericParamDef):
    """
    Defines a numeric parameter definition defined by a lower and upper bound.

    By default, it will represent a parameter space of [lower_bound,
    upper_bound]. However, it can be set to exclude one or both of the bounds.
    """
    lower_bound = None
    upper_bound = None
    include_lower = None
    include_upper = None

    epsilon = None

    def __init__(self, lower_bound, upper_bound,
                 include_lower=True, include_upper=True, epsilon=None):
        """
        Initializes the lower/upper bound defined parameter space.

        Parameters
        ----------
        lower_bound : float
            The lowest possible value
        upper_bound : float
            The highest possible value
        include_lower : bool, optional
            If true (default), lower_bound is the smallest possible value that
            can be returned. If false, all returned values will be greater than
            lower_bound.
        include_upper : bool, optional
            If true (default), upper_bound is the greatest possible value that
            can be returned. If false, all returned values will be less than
            upper_bound.
        epsilon : float, optional
            The tolerance to use if excluding upper/lower. The lowest or
            highest value will be epsilon away from the given lower or upper
            bound. By default, this is ten times the system's float epsilon.

        """
        try:
            lower_bound = float(lower_bound)
            upper_bound = float(upper_bound)
        except:
            raise ValueError("Bounds are not floats.")
        if epsilon is None:
            epsilon = sys.float_info.epsilon * 10
        self.epsilon = epsilon
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.include_lower = include_lower
        self.include_upper = include_upper

    def warp_in(self, unwarped_value):
        modifed_lower = self.lower_bound + (0 if self.include_lower else self.epsilon )
        modifed_upper = self.upper_bound - (0 if self.include_upper else self.epsilon )
        result = ((unwarped_value - (modifed_lower))/
                  (modifed_upper-modifed_lower))
        return [float(result)]

    def warp_out(self, warped_value):
        modifed_lower = self.lower_bound + (0 if self.include_lower else self.epsilon )
        modifed_upper = self.upper_bound - (0 if self.include_upper else self.epsilon )
        result = warped_value[0]*(modifed_upper - modifed_lower) + modifed_lower
        return float(result)

    def warped_size(self):
        return 1

    def is_in_parameter_domain(self, value):
        if not (self.lower_bound < value or
                    (self.lower_bound <= value and self.include_lower)):
            return False
        if not (self.upper_bound > value or
                    (self.upper_bound >= value and self.include_upper)):

            return False
        return True


class PositionParamDef(OrdinalParamDef):
    """
    Defines positions for each of its values.
    """
    positions = None

    def __init__(self, values, positions):
        """
        Initializes PositionParamDef

        Parameters
        ----------
        values : list
            List of the values
        positions : list of floats
            The corresponding positions of these values. Has to have the same
            length as values.
        """
        assert len(values) == len(positions)
        super(PositionParamDef, self).__init__(values)
        self.positions = positions


    def warp_in(self, unwarped_value):
        pos = self.positions[self.values.index(unwarped_value)]
        warped_value = float(pos - min(self.positions))/(max(self.positions) - min(self.positions))
        return warped_value

    def warp_out(self, warped_value):
        if warped_value > 1:
            return self.values[-1]
        if warped_value < 0:
            return self.values[0]
        pos = warped_value * (max(self.positions) - min(self.positions)) + min(self.positions)
        min_pos_idx = 0
        for i, p in enumerate(self.positions):
            if abs(i - pos) < abs(i - self.positions[min_pos_idx]):
                min_pos_idx = i

        return self.values[min_pos_idx]

    def warped_size(self):
        return 1

    def distance(self, valueA, valueB):
        if valueA not in self.values or valueB not in self.values:
            raise ValueError(
                "Values not comparable! Either one or the other is not in the "
                "values domain")
        pos_a = self.positions[self.values.index(valueA)]
        pos_b = self.positions[self.values.index(valueB)]
        diff = abs(pos_a - pos_b)
        return float(diff)


class FixedValueParamDef(PositionParamDef):
    """
    Extension of PositionParamDef, in which the position is equal to the value
    of each entry from values.
    """
    def __init__(self, values):
        positions = []
        for v in values:
            pos = v
            positions.append(pos)
        super(FixedValueParamDef, self).__init__(values, positions)

    def to_dict(self):
        return {"values": self.values,
                "type": self.__class__.__name__}


class EquidistantPositionParamDef(PositionParamDef):
    """
    Extension of PositionParamDef, in which the position of each value is
    equidistant from its neighbours and their order is determined by their
    order in values.
    """
    def __init__(self, values):
        positions = []
        for i, v in enumerate(values):
            pos = float(i)/(len(values)-1)
            positions.append(pos)
        super(EquidistantPositionParamDef, self).__init__(values, positions)


class AsymptoticNumericParamDef(NumericParamDef):
    """
    This represents an asymptotic parameter definition.

    It consists of a fixed border - represented at 0 - and an asymptotic
    border - represented at 1.

    In general, multiplying the input parameter by 1/10th means a multiplication
    of the warped-in value by 1/2. This means that each interval between
    10^-i and 10^-(i-1) is represented by an interval of length 1/2^i on the
    hypercube.

    For example, assume that you want to optimize over a learning rate.
    Generally, they are close to 0, with parameter values (and therefore
    possible optimization values) like 10^-1, 10^-4 or 10^-6. This could be
    done by initializing this class with asymptotic_border = 0 and border = 1.

    Trying to optimize a learning rate decay - which normally is close to 1 -
    one could initialize this class with asymptotic_border = 1 and border = 0.

    Attributes
    ----------
    asymptotic_border : float
        The asymptotic border.
    border : float
        The non-asymptotic border.
    """
    asymptotic_border = None
    border = None

    def __init__(self, asymptotic_border, border):
        """
        Initializes this parameter definition.

        Parameters
        ----------
        asymptotic_border : float
            The asymptotic border.
        border : float
            The non-asymptotic border.
        """
        self.asymptotic_border = float(asymptotic_border)
        self.border = float(border)

    def warp_in(self, unwarped_value):
        if not min(self.asymptotic_border, self.border) <= unwarped_value:
            unwarped_value = min(self.asymptotic_border, self.border)
        if not unwarped_value <= max(self.asymptotic_border, self.border):
            unwarped_value = max(self.asymptotic_border, self.border)
        if unwarped_value == self.border:
            return [0]
        elif unwarped_value == self.asymptotic_border:
            return [1]
        return [(1-2**(math.log(unwarped_value, 10))) *
                (self.border-self.asymptotic_border)+self.asymptotic_border]

    def warp_out(self, warped_value):
        warped_value_single = warped_value[0]
        if warped_value_single < 0:
            warped_value_single = 0
        if warped_value_single > 1:
            warped_value_single = 1
        if warped_value_single == 1:
            return self.asymptotic_border
        elif warped_value_single == 0:
            return self.border
        return 10**math.log(1-(warped_value_single-self.asymptotic_border)/
                            (self.border-self.asymptotic_border), 2)

    def warped_size(self):
        return 1
