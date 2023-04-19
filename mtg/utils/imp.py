# -*- coding: utf-8 -*-
"""
Dynamic module import utility
"""

import os
import re
import sys

sys.path.insert(1, '..')

from importlib import import_module  # pylint:disable=wrong-import-position

from .exc import log_exception  # pylint:disable=wrong-import-position


def list_commands(logger, package='a.b.commands', base_class='BaseCommand') -> list:    # pylint:disable=too-many-locals
    """
    Return list of command classes

    :param package:
    :param base_class:
    :return:
    """
    classes = []
    base = os.path.dirname(os.path.abspath(import_module(package).__file__))
    mod = import_module(package, base_class)
    base_cls = getattr(mod, base_class)
    for top, _, files in os.walk(base):
        for fname in files:
            if fname == '__init__.py':
                continue
            if not fname.endswith('.py'):
                continue
            path = os.path.join(top, fname)
            path = path.replace('.py', '').replace(os.path.sep, '.')
            pkg = re.sub(f'^.+{package}', package, path)
            try:
                module = import_module(pkg)
                objects = dir(module)
            # pylint:disable=broad-except
            except Exception as exc:
                log_exception(logger, exc, description='imp.list_commands failed with: ')
                objects = []
            if not objects:
                continue
            for obj in objects:
                pobj = getattr(module, obj)
                if isinstance(pobj, type) and issubclass(pobj, base_cls) and pobj.__name__ != base_cls.__name__:
                    classes.append(pobj)
    return classes
