##
# @file transform.py
#
# @brief A class decorator that creates a new class with all of the
# attributes of a prototype class converted to a new type.
#
# @author Jive Helix (jivehelix@gmail.com)
# @date 11 Jun 2020
# @copyright Jive Helix
# Licensed under the MIT license. See LICENSE file.

from __future__ import annotations
from typing import TypeVar, Callable, Type, Any, Optional, List
import attr
import warnings
import types
import inspect


T = TypeVar("T")
ProtoType = TypeVar("ProtoType")
AttributeType = TypeVar("AttributeType")


def GetHasName(attributeMaker: Callable[..., AttributeType]) -> bool:
    if isinstance(attributeMaker, type):
        # this is a class
        try: # type: ignore
            init = getattr(attributeMaker, '__init__')
        except AttributeError:
            return False

        signature = inspect.signature(init)
    else:
        signature = inspect.signature(attributeMaker)

    return 'name' in signature.parameters


def Transform(
        protoType: Type[ProtoType],
        attributeMaker: Callable[..., AttributeType],
        init: bool = False,
        namePrefix: Optional[str] = None) -> Callable[[Type[T]], Type[T]]:

    hasName: bool = GetHasName(attributeMaker)

    if hasName:
        # The attributeMaker accepts a name argument
        if namePrefix is not None:
           def MakeName(name: str) -> str:
               assert(namePrefix is not None)
               return namePrefix + "." + name
        else:
           def MakeName(name: str) -> str:
               return name

        def Convert(name: str, protoType: ProtoType) -> AttributeType:
            return attributeMaker(MakeName(name), getattr(protoType, name))
    else:
        # attributeMake has no name argument
        if namePrefix is not None:
            warnings.warn("namePrefix {} will be ignored.".format(namePrefix))

        def Convert(name: str, protoType: ProtoType) -> AttributeType:
            return attributeMaker(getattr(protoType, name))

    def TransformWrapper(class_: Type[T]) -> Type[T]:
        # Set the class vars from protoType
        if hasattr(protoType, '__slots__'):
            setattr(class_, '__slots__', protoType.__slots__)

        classVars: List[str] = []
        for name in dir(protoType):
            if name.startswith("_"):
                # Ignoring dunders and private names
                continue

            member = getattr(protoType, name)
            if type(member) in (types.MethodType, types.FunctionType):
                # Ignoring functions and methods
                continue

            if hasName:
                setattr(class_, name, attributeMaker(MakeName(name), member))
            else:
                setattr(class_, name, attributeMaker(member))

            classVars.append(name)

        setattr(class_, '__transform_class_vars__', classVars)

        instanceVars = list(attr.fields_dict(protoType).keys())
        setattr(class_, '__transform_vars__', instanceVars)

        if init:
            def __init__(self: Any, protoType: ProtoType) -> None:
                for name in instanceVars:
                    setattr(self, name, Convert(name, protoType))

            setattr(class_, "__init__", __init__)

        return class_

    return TransformWrapper



def GetInstanceVars(class_: Type[Any]) -> List[str]:
    return class_.__transform_vars__


def GetClassVars(class_: Type[Any]) -> List[str]:
    return class_.__transform_class_vars__

