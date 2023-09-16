import platform
import pprint

import packaging.version
import pytest

from dirty_equals import Contains, IsApprox, IsInt, IsList, IsNegative, IsOneOf, IsPositive, IsStr
from dirty_equals.version import VERSION


def check_repr_pformat(v, v_repr):
    assert repr(v) == str(v) == v_repr == pprint.pformat(v)


def test_or():
    assert 'foo' == IsStr | IsInt
    assert 1 == IsStr | IsInt
    assert -1 == IsStr | IsNegative | IsPositive

    v = IsStr | IsInt
    with pytest.raises(AssertionError):
        assert 1.5 == v
    assert str(v) == 'IsStr | IsInt'


def test_and():
    assert 4 == IsPositive & IsInt(lt=5)

    v = IsStr & IsInt
    with pytest.raises(AssertionError):
        assert 1 == v
    assert str(v) == 'IsStr & IsInt'


def test_not():
    assert 'foo' != IsInt
    assert 'foo' == ~IsInt


def test_value_eq():
    v = IsStr()

    with pytest.raises(AttributeError, match='value is not available until __eq__ has been called'):
        v.value

    assert 'foo' == v
    assert str(v) == "'foo'"
    check_repr_pformat(v, "'foo'")
    assert v.value == 'foo'


def test_value_ne():
    v = IsStr()

    with pytest.raises(AssertionError):
        assert 1 == v

    assert str(v) == 'IsStr()'
    check_repr_pformat(v, 'IsStr()')
    with pytest.raises(AttributeError, match='value is not available until __eq__ has been called'):
        v.value


def test_dict_compare():
    v = {'foo': 1, 'bar': 2, 'spam': 3}
    assert v == {'foo': IsInt, 'bar': IsPositive, 'spam': ~IsStr}
    assert v == {'foo': IsInt() & IsApprox(1), 'bar': IsPositive() | IsNegative(), 'spam': ~IsStr()}


@pytest.mark.skipif(platform.python_implementation() == 'PyPy', reason='PyPy does not metaclass dunder methods')
def test_not_repr():
    v = ~IsInt
    assert str(v) == '~IsInt'

    with pytest.raises(AssertionError):
        assert 1 == v

    assert str(v) == '~IsInt'


def test_not_repr_instance():
    v = ~IsInt()
    assert str(v) == '~IsInt()'

    with pytest.raises(AssertionError):
        assert 1 == v

    assert str(v) == '~IsInt()'


def test_repr():
    v = ~IsInt
    assert str(v) == '~IsInt'

    assert '1' == v

    assert str(v) == "'1'"


@pytest.mark.parametrize(
    'v,v_repr',
    [
        (IsInt, 'IsInt'),
        (~IsInt, '~IsInt'),
        (IsInt & IsPositive, 'IsInt & IsPositive'),
        (IsInt | IsPositive, 'IsInt | IsPositive'),
        (IsInt(), 'IsInt()'),
        (~IsInt(), '~IsInt()'),
        (IsInt() & IsPositive(), 'IsInt() & IsPositive()'),
        (IsInt() | IsPositive(), 'IsInt() | IsPositive()'),
        (IsInt() & IsPositive, 'IsInt() & IsPositive'),
        (IsInt() | IsPositive, 'IsInt() | IsPositive'),
        (IsPositive & IsInt(lt=5), 'IsPositive & IsInt(lt=5)'),
        (IsOneOf(1, 2, 3), 'IsOneOf(1, 2, 3)'),
    ],
)
def test_repr_class(v, v_repr):
    check_repr_pformat(v, v_repr)


def test_is_approx_without_init():
    assert 1 != IsApprox


def test_ne_repr():
    v = IsInt
    check_repr_pformat(v, 'IsInt')

    assert 'x' != v

    check_repr_pformat(v, 'IsInt')


def test_pprint():
    v = [IsList(length=...), 1, [IsList(length=...), 2], 3, IsInt()]
    lorem = ['lorem', 'ipsum', 'dolor', 'sit', 'amet'] * 2
    with pytest.raises(AssertionError):
        assert [lorem, 1, [lorem, 2], 3, '4'] == v

    assert repr(v) == (f'[{lorem}, 1, [{lorem}, 2], 3, IsInt()]')
    assert pprint.pformat(v) == (
        "[['lorem',\n"
        "  'ipsum',\n"
        "  'dolor',\n"
        "  'sit',\n"
        "  'amet',\n"
        "  'lorem',\n"
        "  'ipsum',\n"
        "  'dolor',\n"
        "  'sit',\n"
        "  'amet'],\n"
        ' 1,\n'
        " [['lorem',\n"
        "   'ipsum',\n"
        "   'dolor',\n"
        "   'sit',\n"
        "   'amet',\n"
        "   'lorem',\n"
        "   'ipsum',\n"
        "   'dolor',\n"
        "   'sit',\n"
        "   'amet'],\n"
        '  2],\n'
        ' 3,\n'
        ' IsInt()]'
    )


@pytest.mark.parametrize(
    'value,dirty',
    [
        (1, IsOneOf(1, 2, 3)),
        (4, ~IsOneOf(1, 2, 3)),
        ([1, 2, 3], Contains(1) | IsOneOf([])),
        ([], Contains(1) | IsOneOf([])),
        ([2], ~(Contains(1) | IsOneOf([]))),
    ],
)
def test_is_one_of(value, dirty):
    assert value == dirty


def test_version():
    packaging.version.parse(VERSION)
