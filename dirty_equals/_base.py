import inspect
from abc import ABCMeta
from inspect import Parameter
from pprint import PrettyPrinter
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, Sequence, Tuple, TypeVar

try:
    from typing import Protocol
except ImportError:
    # Python 3.7 doesn't have Protocol
    Protocol = object  # type: ignore[assignment]

if TYPE_CHECKING:
    from typing import TypeAlias, Union  # noqa: F401

__all__ = 'DirtyEqualsMeta', 'DirtyEquals', 'AnyThing', 'IsOneOf'

ArgsAndKwargs = Tuple[Sequence[Any], Dict[str, Any]]


class DirtyEqualsMeta(ABCMeta):
    def __eq__(self, other: Any) -> bool:
        # this is required as fancy things happen when creating generics which include equals checks, without it,
        # we get some recursive errors
        if self is DirtyEquals or other is Generic or other is Protocol:
            return False
        else:
            try:
                return self() == other
            except TypeError:
                # we don't want to raise a type error here since somewhere deep in pytest it does something like
                # type(a) == type(b), if we raised TypeError we would upset the pytest error message
                return False

    def __or__(self, other: Any) -> 'DirtyOr':  # type: ignore[override]
        return DirtyOr(self, other)

    def __and__(self, other: Any) -> 'DirtyAnd':
        return DirtyAnd(self, other)

    def __invert__(self) -> 'DirtyNot':
        return DirtyNot(self)

    def __hash__(self) -> int:
        return hash(self.__name__)

    def __repr__(self) -> str:
        return self.__name__


T = TypeVar('T')


class DirtyEquals(Generic[T], metaclass=DirtyEqualsMeta):
    """
    Base type for all *dirty-equals* types.
    """

    __slots__ = '_other', '_was_equal'

    def __init__(self) -> None:
        self._other: Any = None
        self._was_equal: Optional[bool] = None

    def equals(self, other: Any) -> bool:
        """
        Abstract method, must be implemented by subclasses.

        `TypeError` and `ValueError` are caught in `__eq__` and indicate `other` is not equals to this type.
        """
        raise NotImplementedError()

    @property
    def value(self) -> T:
        """
        Property to get the value last successfully compared to this object.

        This is seldom very useful, put it's provided for completeness.

        Example of usage:

        ```py title=".values"
        from dirty_equals import IsStr

        token_is_str = IsStr(regex=r't-.+')
        assert 't-123' == token_is_str

        print(token_is_str.value)
        #> t-123
        ```
        """
        if self._was_equal:
            return self._other
        else:
            raise AttributeError('value is not available until __eq__ has been called')

    def __eq__(self, other: Any) -> bool:
        self._other = other
        try:
            self._was_equal = self.equals(other)
        except (TypeError, ValueError):
            self._was_equal = False

        return self._was_equal

    def __ne__(self, other: Any) -> bool:
        # We don't set _was_equal to avoid strange errors in pytest
        self._other = other
        try:
            return not self.equals(other)
        except (TypeError, ValueError):
            return True

    def __or__(self, other: Any) -> 'DirtyOr':
        return DirtyOr(self, other)

    def __and__(self, other: Any) -> 'DirtyAnd':
        return DirtyAnd(self, other)

    def __invert__(self) -> 'DirtyNot':
        return DirtyNot(self)

    def _repr_args_kwargs(self) -> ArgsAndKwargs:
        args = []
        kwargs = {}
        for name, param in self._signature_params().items():
            if not hasattr(self, name):
                continue
            value = getattr(self, name)
            if param.kind == param.POSITIONAL_ONLY:
                args.append(value)
            elif param.kind == param.POSITIONAL_OR_KEYWORD:
                if param.default is param.empty:
                    args.append(value)
                else:
                    kwargs[name] = value
            elif param.kind == param.KEYWORD_ONLY:
                kwargs[name] = value
            elif param.kind == param.VAR_POSITIONAL:
                args.extend(value)
            elif param.kind == param.VAR_KEYWORD:
                kwargs.update(value)
        return args, kwargs

    def _repr_ne(self) -> str:
        params = self._signature_params()
        args, kwargs = self._repr_args_kwargs()
        args_reprs = [repr(a) for a in args]
        args_reprs += [f'{k}={v!r}' for k, v in kwargs.items() if not (k in params and params[k].default == v)]
        return f'{self.__class__.__name__}({", ".join(args_reprs)})'

    def _signature_params(self) -> MappingProxyType[str, Parameter]:
        sig = inspect.signature(self.__init__)  # type: ignore[misc]
        return sig.parameters

    def __repr__(self) -> str:
        if self._was_equal:
            # if we've got the correct value return it to aid in diffs
            return repr(self._other)
        else:
            # else return something which explains what's going on.
            return self._repr_ne()

    def _pprint_format(self, pprinter: PrettyPrinter, *args: Any, **kwargs: Any) -> str:
        # pytest diffs use pprint to format objects, so we patch pprint to call this method
        # for DirtyEquals objects. So this method needs to follow the same pattern as __repr__.
        # We check that the protected _format method actually exists
        # to be safe and to make linters happy.
        if self._was_equal and hasattr(pprinter, '_format'):
            return pprinter._format(self._other, *args, **kwargs)
        else:
            return repr(self)  # i.e. self._repr_ne() (for now)


# Patch pprint to call _pprint_format for DirtyEquals objects
# Check that the protected attribute _dispatch exists to be safe and to make linters happy.
# The reason we modify _dispatch rather than _format
# is that pytest sometimes uses a subclass of PrettyPrinter which overrides _format.
if hasattr(PrettyPrinter, '_dispatch'):
    PrettyPrinter._dispatch[DirtyEquals.__repr__] = lambda pprinter, obj, *args, **kwargs: obj._pprint_format(
        pprinter, *args, **kwargs
    )


InstanceOrType: 'TypeAlias' = 'Union[DirtyEquals[Any], DirtyEqualsMeta]'


class DirtyOr(DirtyEquals[Any]):
    def __init__(self, a: 'InstanceOrType', b: 'InstanceOrType', *extra: 'InstanceOrType'):
        self.dirties = (a, b) + extra
        super().__init__()

    def equals(self, other: Any) -> bool:
        return any(d == other for d in self.dirties)

    def _repr_ne(self) -> str:
        return ' | '.join(_repr_ne(d) for d in self.dirties)


class DirtyAnd(DirtyEquals[Any]):
    def __init__(self, a: InstanceOrType, b: InstanceOrType, *extra: InstanceOrType):
        self.dirties = (a, b) + extra
        super().__init__()

    def equals(self, other: Any) -> bool:
        return all(d == other for d in self.dirties)

    def _repr_ne(self) -> str:
        return ' & '.join(_repr_ne(d) for d in self.dirties)


class DirtyNot(DirtyEquals[Any]):
    def __init__(self, subject: InstanceOrType):
        self.subject = subject
        super().__init__()

    def equals(self, other: Any) -> bool:
        return self.subject != other

    def _repr_ne(self) -> str:
        return f'~{_repr_ne(self.subject)}'


def _repr_ne(v: InstanceOrType) -> str:
    if isinstance(v, DirtyEqualsMeta):
        return repr(v)
    else:
        return v._repr_ne()


class AnyThing(DirtyEquals[Any]):
    """
    A type which matches any value. `AnyThing` isn't generally very useful on its own, but can be used within
    other comparisons.

    ```py title="AnyThing"
    from dirty_equals import AnyThing, IsList, IsStrictDict

    assert 1 == AnyThing
    assert 'foobar' == AnyThing
    assert [1, 2, 3] == AnyThing

    assert [1, 2, 3] == IsList(AnyThing, 2, 3)

    assert {'a': 1, 'b': 2, 'c': 3} == IsStrictDict(a=1, b=AnyThing, c=3)
    ```
    """

    def equals(self, other: Any) -> bool:
        return True


class IsOneOf(DirtyEquals[Any]):
    """
    A type which checks that the value is equal to one of the given values.

    Can be useful with boolean operators.
    """

    def __init__(self, expected_value: Any, *more_expected_values: Any) -> None:
        """
        Args:
            expected_value: Expected value for equals to return true.
            *more_expected_values: More expected values for equals to return true.

        ```py title="IsOneOf"
        from dirty_equals import Contains, IsOneOf

        assert 1 == IsOneOf(1, 2, 3)
        assert 4 != IsOneOf(1, 2, 3)
        # check that a list either contain 1 or is empty
        assert [1, 2, 3] == Contains(1) | IsOneOf([])
        assert [] == Contains(1) | IsOneOf([])
        ```
        """
        self.expected_values: Tuple[Any, ...] = (expected_value,) + more_expected_values
        super().__init__()

    def _repr_args_kwargs(self) -> ArgsAndKwargs:
        return self.expected_values, {}

    def equals(self, other: Any) -> bool:
        return any(other == e for e in self.expected_values)
