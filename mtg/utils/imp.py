# -*- coding: utf-8 -*-
"""

"""

import os
import re
import sys
sys.path.insert(1, '..')

from .exc import log_exception

from importlib import import_module


def list_commands(logger, package='a.b.commands', baseClass='BaseCommand'):
    """
    Return list of command classes

    :param package:
    :param baseClass:
    :return:
    """
    classes = []
    base = os.path.dirname(os.path.abspath(import_module(package).__file__))
    mod = import_module(package, baseClass)
    base_cls = getattr(mod, baseClass)
    for top, _, files in os.walk(base):
        for fname in files:
            if fname == '__init__.py':
                continue
            if not fname.endswith('.py'):
                continue
            path = os.path.join(top, fname)
            path = path.replace('.py', '').replace(os.path.sep, '.')
            pkg = re.sub('^.+' + package, package, path)
            try:
                module = import_module(pkg)
                objects = dir(module)
            # pylint:disable=broad-except
            except Exception as exc:
                log_exception(exc, description='imp.list_commands failed with: ')
                objects = []
            if not objects:
                continue
            for obj in objects:
                pobj = getattr(module, obj)
                if type(pobj) == type and issubclass(pobj, base_cls) and pobj.__name__ != base_cls.__name__:
                    classes.append(pobj)
    return classes
