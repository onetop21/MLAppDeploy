import os
import sys

from typing import Optional

from .node import Node
from .project import Project
from .app import App
from .check import Check

from mlad.cli import config as config_core
from functools import lru_cache


class ClassPropertyDescriptor(object):

    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self, obj, value):
        if not self.fset:
            raise AttributeError("can't set attribute")
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self, func):
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self


def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)

    return ClassPropertyDescriptor(func)


class API:

    @classproperty
    @lru_cache(maxsize=None)
    def address(cls) -> Optional[str]:
        try:
            config = config_core.get()
            return config_core.obtain_server_address(config)
        except Exception:
            return None

    @classproperty
    @lru_cache(maxsize=None)
    def session(cls) -> Optional[str]:
        try:
            return config_core.get()['session']
        except Exception:
            return None

    @classproperty
    @lru_cache(maxsize=None)
    def node(cls) -> Node:
        return Node(cls.address, cls.session)

    @classproperty
    @lru_cache(maxsize=None)
    def project(cls) -> Project:
        return Project(cls.address, cls.session)

    @classproperty
    @lru_cache(maxsize=None)
    def app(cls) -> App:
        return App(cls.address, cls.session)

    @classproperty
    @lru_cache(maxsize=None)
    def check(cls) -> Check:
        return Check(cls.address, cls.session)
