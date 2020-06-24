##
# @file plugin.py
# 
# @brief Loads a custom mypy plugin.
# 
# @author Jive Helix (jivehelix@gmail.com)
# @date 11 Jun 2020
# @copyright Jive Helix
# Licensed under the MIT license. See LICENSE file.

from __future__ import annotations
from typing import Optional, Callable
import mypy.plugin
from transform_plugin import (
    transform_makers,
    transform_class_maker_callback)

class TransformPlugin(mypy.plugin.Plugin):
    def get_class_decorator_hook(self, fullName: str) \
            -> Optional[Callable[[mypy.plugin.ClassDefContext], None]]:

        if fullName in transform_makers:
            return transform_class_maker_callback

        return None

def plugin(ignored: str):
    return TransformPlugin
