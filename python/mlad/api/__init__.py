import os
import sys
from .node import Node
from .service import Service
from .project import Project

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
    def config(cls):
        return config_core.get()

    @classproperty
    @lru_cache(maxsize=None)
    def node(cls):
        return Node(cls.config)

    @classproperty
    @lru_cache(maxsize=None)
    def project(cls):
        return Project(cls.config)

    @classproperty
    @lru_cache(maxsize=None)
    def service(cls):
        return Service(cls.config)
