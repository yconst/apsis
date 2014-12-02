from abc import ABCMeta, abstractmethod
import random

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

        Parameters
        ----------
        value: object
            Tests whether the object is in the parameter domain.

        Returns
        -------
        is_in_parameter_domain: bool
            True iff value is in the parameter domain as defined by this
            instance.
        """
        pass

    def distance(self, valueA, valueB):
        if valueA == valueB:
            return 0
        return 1


class ComparableParameterDef(object):
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
        one: object in parameter definition
            The first value used in comparison.

        two: object in parameter definition
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
        values: list
            A list of values which are the possible values that are in this
            parameter definition.

        Raises
        ------
        ValueError:
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


class OrdinalParamDef(NominalParamDef, ComparableParameterDef):
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
        if valueA not in self.values or valueB not in self.values:
            raise ValueError(
                "Values not comparable! Either one or the other is not in the "
                "values domain")
        indexA = self.values.index(valueA)
        indexB = self.values.index(valueB)
        diff = abs(indexA - indexB)
        return float(diff)/len(self.values)


class NumericParamDef(ParamDef, ComparableParameterDef):
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
        warping_in: function
            warping_in must take a value and return a corresponding value in
            the [0, 1] space.
        warping_out: function
            warping_out is the reverse function to warping_in.
        """
        super(NumericParamDef, self).__init__()
        self.warping_in = warping_in
        self.warping_out = warping_out

    def is_in_parameter_domain(self, value):
        """
        Uses the warp_out function for tests.
        """
        if self.warp_out(0) <= value <= self.warp_out(1):
            return True
        return False

    def warp_in(self, value_in):
        """
        Warps value_in into the [0, 1] space.

        Parameters
        ----------
        value_in: float
            The input value

        Returns
        -------
        value_in_scaled: float in [0, 1]
            The scaled output value.
        """
        return self.warping_in(value_in)

    def warp_out(self, value_out):
        """
        Warps value_out out of the [0, 1] space.

        Parameters
        ----------
        value_out: float in [0, 1]
            The output value.

        Returns
        -------
        value_out_unscaled: float
            The unscaled value in the parameter space.
        """
        return self.warping_out(value_out)

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
        if valueA < valueB:
            return -1
        elif valueA > valueB:
            return 1
        else:
            return 0


class LowerUpperNumericParamDef(NumericParamDef):
    """
    Defines a numeric parameter definition defined by a lower and upper bound.
    """
    x_min = None
    x_max = None

    def __init__(self, lower_bound, upper_bound):
        """
        Initializes the lower/upper bound defined parameter space.

        Parameters
        ----------
        lower_bound: float
            The lowest possible value

        upper_bound: float
            The highest possible value
        """
        self.x_min = lower_bound
        self.x_max = upper_bound

    def warp_in(self, value_in):
        return (value_in - self.x_min)/(self.x_max-self.x_min)

    def warp_out(self, value_out):
        return value_out*(self.x_max - self.x_min) + self.x_min

    def is_in_parameter_domain(self, value):
        return self.x_min <= value <= self.x_max


class PositionParamDef(OrdinalParamDef):
    positions = None

    def __init__(self, values, positions):
        assert len(values) == len(positions)
        super(PositionParamDef, self).__init__(values)
        self.positions = positions

    def warp_in(self, value_in):
        pos = self.positions[self.values.index(value_in)]
        value_out = (pos - self.positions[0])/(self.positions[-1]-self.positions[0])
        return value_out

    def warp_out(self, value_out):
        if value_out > self.positions[-1]:
            return self.values[-1]
        if value_out < self.positions[0]:
            return self.values[0]
        for i, p in enumerate(self.positions):
            if p >= value_out:
                return self.values[i]

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
    def __init__(self, values):
        positions = []
        pos = 0
        for v in values:
            pos += v
            positions.append(pos)
        super(FixedValueParamDef, self).__init__(values, positions)