from collections import OrderedDict
import json
import os
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, Callable, List, Dict, Set, Tuple, Union
import unittest
from unittest import TestCase
from typing_extensions import Literal

from tap.utils import (
    has_git,
    get_class_column,
    get_class_variables,
    get_git_root,
    get_git_url,
    has_uncommitted_changes,
    type_to_str,
    get_literals,
    TupleTypeEnforcer,
    _nested_replace_type,
    define_python_object_encoder,
    UnpicklableObject,
    as_python_object
)


class GitTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.prev_dir = os.getcwd()
        os.chdir(self.temp_dir.name)
        subprocess.check_output(['git', 'init'])
        self.url = 'https://github.com/test_account/test_repo'
        subprocess.check_output(['git', 'remote', 'add', 'origin', f'{self.url}.git'])
        subprocess.check_output(['touch', 'README.md'])
        subprocess.check_output(['git', 'add', 'README.md'])
        subprocess.check_output(['git', 'commit', '-m', 'Initial commit'])

    def tearDown(self) -> None:
        os.chdir(self.prev_dir)

        # Add permissions to temporary directory to enable cleanup in Windows
        for root, dirs, files in os.walk(self.temp_dir.name):
            for name in dirs + files:
                os.chmod(os.path.join(root, name), 0o777)

        self.temp_dir.cleanup()

    def test_has_git_true(self) -> None:
        self.assertTrue(has_git())

    def test_has_git_false(self) -> None:
        with TemporaryDirectory() as temp_dir_no_git:
            os.chdir(temp_dir_no_git)
            self.assertFalse(has_git())
        os.chdir(self.temp_dir.name)

    def test_get_git_root(self) -> None:
        self.assertTrue(get_git_root() in f'/private{self.temp_dir.name}')

    def test_get_git_root_subdir(self) -> None:
        os.makedirs(os.path.join(self.temp_dir.name, 'subdir'))
        self.assertTrue(get_git_root() in f'/private{self.temp_dir.name}')

    def test_get_git_url_https(self) -> None:
        self.assertEqual(get_git_url(commit_hash=False), self.url)

    def test_get_git_url_https_hash(self) -> None:
        url = f'{self.url}/tree/'
        self.assertEqual(get_git_url(commit_hash=True)[:len(url)], url)

    def test_get_git_url_ssh(self) -> None:
        subprocess.run(['git', 'remote', 'set-url', 'origin', 'git@github.com:test_account/test_repo.git'])
        self.assertEqual(get_git_url(commit_hash=False), self.url)

    def test_get_git_url_ssh_hash(self) -> None:
        subprocess.run(['git', 'remote', 'set-url', 'origin', 'git@github.com:test_account/test_repo.git'])
        url = f'{self.url}/tree/'
        self.assertEqual(get_git_url(commit_hash=True)[:len(url)], url)

    def test_get_git_url_https_enterprise(self) -> None:
        true_url = 'https://github.tap.com/test_account/test_repo'
        subprocess.run(['git', 'remote', 'set-url', 'origin', f'{true_url}.git'])
        self.assertEqual(get_git_url(commit_hash=False), true_url)

    def test_get_git_url_https_hash_enterprise(self) -> None:
        true_url = 'https://github.tap.com/test_account/test_repo'
        subprocess.run(['git', 'remote', 'set-url', 'origin', f'{true_url}.git'])
        url = f'{true_url}/tree/'
        self.assertEqual(get_git_url(commit_hash=True)[:len(url)], url)

    def test_get_git_url_ssh_enterprise(self) -> None:
        true_url = 'https://github.tap.com/test_account/test_repo'
        subprocess.run(['git', 'remote', 'set-url', 'origin', 'git@github.tap.com:test_account/test_repo.git'])
        self.assertEqual(get_git_url(commit_hash=False), true_url)

    def test_get_git_url_ssh_hash_enterprise(self) -> None:
        true_url = 'https://github.tap.com/test_account/test_repo'
        subprocess.run(['git', 'remote', 'set-url', 'origin', 'git@github.tap.com:test_account/test_repo.git'])
        url = f'{true_url}/tree/'
        self.assertEqual(get_git_url(commit_hash=True)[:len(url)], url)

    def test_has_uncommitted_changes_false(self) -> None:
        self.assertFalse(has_uncommitted_changes())

    def test_has_uncommited_changes_true(self) -> None:
        subprocess.run(['touch', 'main.py'])
        self.assertTrue(has_uncommitted_changes())


class TypeToStrTests(TestCase):
    def test_type_to_str(self) -> None:
        self.assertEqual(type_to_str(str), 'str')
        self.assertEqual(type_to_str(int), 'int')
        self.assertEqual(type_to_str(float), 'float')
        self.assertEqual(type_to_str(bool), 'bool')
        self.assertEqual(type_to_str(Any), 'Any')
        self.assertEqual(type_to_str(Callable[[str], str]), 'Callable[[str], str]')
        self.assertEqual(type_to_str(Callable[[str, int], Tuple[float, bool]]),
                         'Callable[[str, int], Tuple[float, bool]]')
        self.assertEqual(type_to_str(List[int]), 'List[int]')
        self.assertEqual(type_to_str(List[str]), 'List[str]')
        self.assertEqual(type_to_str(List[float]), 'List[float]')
        self.assertEqual(type_to_str(List[bool]), 'List[bool]')
        self.assertEqual(type_to_str(Set[int]), 'Set[int]')
        self.assertEqual(type_to_str(Dict[str, int]), 'Dict[str, int]')
        self.assertEqual(type_to_str(Union[List[int], Dict[float, bool]]), 'Union[List[int], Dict[float, bool]]')


class ClassColumnTests(TestCase):
    def test_column_simple(self):
        class SimpleColumn:
            arg = 2
        self.assertEqual(get_class_column(SimpleColumn), 12)

    def test_column_comment(self):
        class CommentColumn:
            """hello
            there


            hi
            """
            arg = 2
        self.assertEqual(get_class_column(CommentColumn), 12)

    def test_column_space(self):
        class SpaceColumn:

            arg = 2
        self.assertEqual(get_class_column(SpaceColumn), 12)

    def test_column_method(self):
        class FuncColumn:
            def func(self):
                pass

        self.assertEqual(get_class_column(FuncColumn), 12)


class ClassVariableTests(TestCase):
    def test_no_variables(self):
        class NoVariables:
            pass
        self.assertEqual(get_class_variables(NoVariables), OrderedDict())

    def test_one_variable(self):
        class OneVariable:
            arg = 2
        class_variables = OrderedDict()
        class_variables['arg'] = {'comment': ''}
        self.assertEqual(get_class_variables(OneVariable), class_variables)

    def test_multiple_variable(self):
        class MultiVariable:
            arg_1 = 2
            arg_2 = 3
        class_variables = OrderedDict()
        class_variables['arg_1'] = {'comment': ''}
        class_variables['arg_2'] = {'comment': ''}
        self.assertEqual(get_class_variables(MultiVariable), class_variables)

    def test_typed_variables(self):
        class TypedVariable:
            arg_1: str
            arg_2: int = 3
        class_variables = OrderedDict()
        class_variables['arg_1'] = {'comment': ''}
        class_variables['arg_2'] = {'comment': ''}
        self.assertEqual(get_class_variables(TypedVariable), class_variables)

    def test_separated_variables(self):
        class SeparatedVariable:
            """Comment

            """
            arg_1: str

            # Hello
            def func(self):
                pass

            arg_2: int = 3
            """More comment"""
        class_variables = OrderedDict()
        class_variables['arg_1'] = {'comment': ''}
        class_variables['arg_2'] = {'comment': 'More comment'}
        self.assertEqual(get_class_variables(SeparatedVariable), class_variables)

    def test_commented_variables(self):
        class CommentedVariable:
            """Comment

            """
            arg_1: str  # Arg 1 comment

            # Hello
            def func(self):
                pass

            arg_2: int = 3  # Arg 2 comment
            arg_3   :   Dict[str, int]      # noqa E203,E262   Poorly   formatted comment
            """More comment"""
        class_variables = OrderedDict()
        class_variables['arg_1'] = {'comment': 'Arg 1 comment'}
        class_variables['arg_2'] = {'comment': 'Arg 2 comment'}
        class_variables['arg_3'] = {'comment': 'noqa E203,E262   Poorly   formatted comment More comment'}
        self.assertEqual(get_class_variables(CommentedVariable), class_variables)

    def test_bad_spacing_multiline(self):
        class TrickyMultiline:
            """   This is really difficult

        so
            so very difficult
            """
            foo: str = 'my'  # Header line

            """    Footer
T
        A
                P

            multi
            line!!
                """

        class_variables = OrderedDict()
        comment = 'Header line Footer\nT\n        A\n                P\n\n            multi\n            line!!'
        class_variables['foo'] = {'comment': comment}
        self.assertEqual(get_class_variables(TrickyMultiline), class_variables)

    def test_single_quote_multiline(self):
        class SingleQuoteMultiline:
            bar: int = 0
            '''biz baz'''

        class_variables = OrderedDict()
        class_variables['bar'] = {'comment': 'biz baz'}
        self.assertEqual(get_class_variables(SingleQuoteMultiline), class_variables)

    def test_functions_with_docs_multiline(self):
        class FunctionsWithDocs:
            i: int = 0

            def f(self):
                """Function"""
                a: str = 'hello'  # noqa F841
                """with docs"""

        class_variables = OrderedDict()
        class_variables['i'] = {'comment': ''}
        self.assertEqual(get_class_variables(FunctionsWithDocs), class_variables)


class GetLiteralsTests(TestCase):
    def test_get_literals_string(self) -> None:
        literal_f, shapes = get_literals(Literal['square', 'triangle', 'circle'], 'shape')
        self.assertEqual(shapes, ['square', 'triangle', 'circle'])
        self.assertEqual(literal_f('square'), 'square')
        self.assertEqual(literal_f('triangle'), 'triangle')
        self.assertEqual(literal_f('circle'), 'circle')

    def test_get_literals_primitives(self) -> None:
        literals = [True, 'one', 2, 3.14]
        literal_f, prims = get_literals(Literal[True, 'one', 2, 3.14], 'number')
        self.assertEqual(prims, literals)
        self.assertEqual([literal_f(str(p)) for p in prims], literals)

    def test_get_literals_uniqueness(self) -> None:
        with self.assertRaises(ValueError):
            get_literals(Literal['two', 2, '2'], 'number')

    def test_get_literals_empty(self) -> None:
        literal_f, prims = get_literals(Literal, 'hi')
        self.assertEqual(prims, [])


class TupleTypeEnforcerTests(TestCase):
    def test_tuple_type_enforcer_zero_types(self):
        enforcer = TupleTypeEnforcer(types=[])
        with self.assertRaises(IndexError):
            enforcer('hi')

    def test_tuple_type_enforcer_one_type_str(self):
        enforcer = TupleTypeEnforcer(types=[str])
        self.assertEqual(enforcer('hi'), 'hi')

    def test_tuple_type_enforcer_one_type_int(self):
        enforcer = TupleTypeEnforcer(types=[int])
        self.assertEqual(enforcer('123'), 123)

    def test_tuple_type_enforcer_one_type_float(self):
        enforcer = TupleTypeEnforcer(types=[float])
        self.assertEqual(enforcer('3.14159'), 3.14159)

    def test_tuple_type_enforcer_one_type_bool(self):
        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('True'), True)

        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('true'), True)

        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('False'), False)

        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('false'), False)

        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('tRu'), True)

        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('faL'), False)

        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('1'), True)

        enforcer = TupleTypeEnforcer(types=[bool])
        self.assertEqual(enforcer('0'), False)

    def test_tuple_type_enforcer_multi_types_same(self):
        enforcer = TupleTypeEnforcer(types=[str, str])
        args = ['hi', 'bye']
        output = [enforcer(arg) for arg in args]
        self.assertEqual(output, args)

        enforcer = TupleTypeEnforcer(types=[int, int, int])
        args = [123, 456, -789]
        output = [enforcer(str(arg)) for arg in args]
        self.assertEqual(output, args)

        enforcer = TupleTypeEnforcer(types=[float, float, float, float])
        args = [1.23, 4.56, -7.89, 3.14159]
        output = [enforcer(str(arg)) for arg in args]
        self.assertEqual(output, args)

        enforcer = TupleTypeEnforcer(types=[bool, bool, bool, bool, bool])
        args = ['True', 'False', '1', '0', 'tru']
        true_output = [True, False, True, False, True]
        output = [enforcer(str(arg)) for arg in args]
        self.assertEqual(output, true_output)

    def test_tuple_type_enforcer_multi_types_different(self):
        enforcer = TupleTypeEnforcer(types=[str, int, float, bool])
        args = ['hello', 77, 0.2, 'tru']
        true_output = ['hello', 77, 0.2, True]
        output = [enforcer(str(arg)) for arg in args]
        self.assertEqual(output, true_output)

    def test_tuple_type_enforcer_infinite(self):
        enforcer = TupleTypeEnforcer(types=[int], loop=True)
        args = [1, 2, -5, 20]
        output = [enforcer(str(arg)) for arg in args]
        self.assertEqual(output, args)


class NestedReplaceTypeTests(TestCase):
    def test_nested_replace_type_notype(self):
        obj = ['123', 4, 5, ('hello', 4.4)]
        replaced_obj = _nested_replace_type(obj, bool, int)
        self.assertEqual(obj, replaced_obj)

    def test_nested_replace_type_unnested(self):
        obj = ['123', 4, 5, ('hello', 4.4), True, False, 'hi there']
        replaced_obj = _nested_replace_type(obj, tuple, list)
        correct_obj = ['123', 4, 5, ['hello', 4.4], True, False, 'hi there']
        self.assertNotEqual(obj, replaced_obj)
        self.assertEqual(correct_obj, replaced_obj)

    def test_nested_replace_type_nested(self):
        obj = ['123', [4, (1, 2, (3, 4))], 5, ('hello', (4,), 4.4), {'1': [2, 3, [{'2': (3, 10)}, ' hi ']]}]
        replaced_obj = _nested_replace_type(obj, tuple, list)
        correct_obj = ['123', [4, [1, 2, [3, 4]]], 5, ['hello', [4], 4.4], {'1': [2, 3, [{'2': [3, 10]}, ' hi ']]}]
        self.assertNotEqual(obj, replaced_obj)
        self.assertEqual(correct_obj, replaced_obj)


class Person:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Person) and self.name == other.name


class PythonObjectEncoderTests(TestCase):
    def test_python_object_encoder_simple_types(self):
        obj = [1, 2, 'hi', 'bye', 7.3, [1, 2, 'blarg'], True, False, None]
        dumps = json.dumps(obj, indent=4, sort_keys=True, cls=define_python_object_encoder())
        recreated_obj = json.loads(dumps, object_hook=as_python_object)
        self.assertEqual(recreated_obj, obj)

    def test_python_object_encoder_tuple(self):
        obj = [1, 2, 'hi', 'bye', 7.3, (1, 2, 'blarg'), [('hi', 'bye'), 2], {'hi': {'bye': (3, 4)}}, True, False, None]
        dumps = json.dumps(obj, indent=4, sort_keys=True, cls=define_python_object_encoder())
        recreated_obj = json.loads(dumps, object_hook=as_python_object)
        self.assertEqual(recreated_obj, obj)

    def test_python_object_encoder_set(self):
        obj = [1, 2, 'hi', 'bye', 7.3, {1, 2, 'blarg'}, [{'hi', 'bye'}, 2], {'hi': {'bye': {3, 4}}}, True, False, None]
        dumps = json.dumps(obj, indent=4, sort_keys=True, cls=define_python_object_encoder())
        recreated_obj = json.loads(dumps, object_hook=as_python_object)
        self.assertEqual(recreated_obj, obj)

    def test_python_object_encoder_complex(self):
        obj = [1, 2, 'hi', 'bye', 7.3, {1, 2, 'blarg'}, [('hi', 'bye'), 2], {'hi': {'bye': {3, 4}}}, True, False, None,
               (Person('tappy'), Person('tapper'))]
        dumps = json.dumps(obj, indent=4, sort_keys=True, cls=define_python_object_encoder())
        recreated_obj = json.loads(dumps, object_hook=as_python_object)
        self.assertEqual(recreated_obj, obj)

    def test_python_object_encoder_unpicklable(self):
        class CannotPickleThis:
            """Da na na na. Can't pickle this. """
            def __init__(self):
                self.x = 1

        obj = [1, CannotPickleThis()]
        expected_obj = [1, UnpicklableObject()]
        with self.assertRaises(ValueError):
            dumps = json.dumps(obj, indent=4, sort_keys=True, cls=define_python_object_encoder())

        dumps = json.dumps(obj, indent=4, sort_keys=True, cls=define_python_object_encoder(True))
        recreated_obj = json.loads(dumps, object_hook=as_python_object)
        self.assertEqual(recreated_obj, expected_obj)


if __name__ == '__main__':
    unittest.main()
