# -*- coding: utf-8 -*-
"""
Dynamic module import utility
"""

import os
import re
import sys
from importlib import import_module
from typing import Any, List, Type

sys.path.insert(1, '..')

from .exc import log_exception  # pylint:disable=wrong-import-position


def list_classes(logger: Any, package: str = 'a.b.classes', base_class: str = 'BaseClass') -> List[Type[Any]]:    # pylint:disable=too-many-locals
    """
    Return list of command classes

    :param package:
    :param base_class:
    :return:
    """
    classes: List[Type[Any]] = []
    imported_module = import_module(package)
    module_file = imported_module.__file__
    if module_file is None:
        return classes
    base = os.path.dirname(os.path.abspath(module_file))
    mod = import_module(package, base_class)
    base_cls = getattr(mod, base_class)

    # Whitelist of allowed packages for security
    allowed_packages = ['mtg.bot', 'mtg.connection', 'mtg.filter', 'mtg.webapp']

    for top, _, files in os.walk(base):
        for fname in files:
            if fname == '__init__.py':
                continue
            if not fname.endswith('.py'):
                continue
            path = os.path.join(top, fname)
            path = path.replace('.py', '').replace(os.path.sep, '.')
            pkg = re.sub(f'^.+{package}', package, path)

            # Security check: only allow whitelisted packages
            if not any(pkg.startswith(allowed_pkg) for allowed_pkg in allowed_packages):
                logger.warning(f"Skipping non-whitelisted package: {pkg}")
                continue

            try:
                module = import_module(pkg)
                objects = dir(module)
            # pylint:disable=broad-except
            except Exception as exc:
                log_exception(logger, exc, description='imp.list_classes failed with: ')
                objects = []
            if not objects:
                continue
            for obj in objects:
                pobj = getattr(module, obj)
                if isinstance(pobj, type) and issubclass(pobj, base_cls) and pobj.__name__ != base_cls.__name__:
                    classes.append(pobj)
    return classes
