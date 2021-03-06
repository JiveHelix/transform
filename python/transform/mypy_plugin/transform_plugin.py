##
# @file transform.py
#
# @brief A custom plugin to type check transformed classes.
#
# @author Jive Helix (jivehelix@gmail.com)
# @date 11 Jun 2020
# @copyright Jive Helix
# Licensed under the MIT license. See LICENSE file.

from __future__ import annotations

import copy
import mypy.plugin
import mypy.types

from mypy.nodes import (
    Argument,
    Var,
    ARG_POS,
    MemberExpr,
    TypeInfo,
    FuncDef,
    Decorator,
    CallExpr)

from mypy.plugins.common import add_method_to_class


transform_makers = {"transform.transform.Transform", }

typeInfoByProtoTypeName: Dict[str, TypeInfo] = {}


class LookupMemberError(RuntimeError):
    pass


def lookup_member_expr(
        context: mypy.plugin.ClassDefContext,
        node: MemberExpr) -> TypeInfo:

    node_name = node.name
    nodeType = context.api.lookup_fully_qualified_or_none(node.expr.fullname)

    if nodeType.node.name == node_name:
        # This is the type we were looking for
        return nodeType.node

    if node_name not in nodeType.node.names:
        raise LookupMemberError(
            "Unable to find node name: {}".format(node_name))

    node_member = nodeType.node.names[node_name].node
    if isinstance(node_member, TypeInfo):
        return node_member

    if not isinstance(node_member, Decorator):
        # We are looking for a decorated classmethod
        raise LookupMemberError("Expected decorator")

    if not node_member.var.is_classmethod:
        raise LookupMemberError("Expected classmethod")

    # Return the type of the class
    return node_member.var.info


def transform_class_maker_callback(
        context: mypy.plugin.ClassDefContext) -> None:
    proto_type = context.reason.args[0]
    attribute_type = context.reason.args[1]

    try:
        init = ('True' == context.reason.args[2].name)
    except IndexError:
        init = False

    proto_type_node = proto_type.node

    if isinstance(attribute_type, CallExpr):
        functor = attribute_type.callee.node
        functorCall = functor.names['__call__']
        attribute_type_node = functorCall.node.type.ret_type.type
    else:
        attribute_type_node = attribute_type.node

    # Multiple passes may be required to resolve all type information.
    # We must def until all nodes are defined.
    if not context.api.final_iteration:
        if proto_type_node is None or attribute_type_node is None:
            context.api.defer()
            return

    if proto_type_node is None:
        if not isinstance(proto_type, MemberExpr):
            print("No way to lookup prototype node.")
            return

        # proto_type may be named in another module
        proto_type_node = lookup_member_expr(context, proto_type)

    if attribute_type_node is None:
        if not isinstance(attribute_type, MemberExpr):
            print("No way to lookup attribute_type node.")
            return

        try:
            # attribute_type may be named in another module
            attribute_type_node = lookup_member_expr(context, attribute_type)
        except MemberLookupError as error:
            print("Member lookup failed: {}".format(error))
            return

    if isinstance(attribute_type_node, FuncDef):
        # This is a free standing function
        # Get the attribute type from the return value
        ret_type = attribute_type_node.type.ret_type

        if isinstance(ret_type, mypy.types.Instance):
            attribute_type_node = attribute_type_node.type.ret_type.type
        elif isinstance(ret_type, mypy.types.UnboundType):
            if not context.api.final_iteration:
                # wait until the type has been fully analyzed.
                context.api.defer()
                return

            # How is the ret_type still UnboundType?
            # Is this a bug?
            print(
                "Unable to find return type for {}. "
                "Prefer a class or a classmethod".format(
                    attribute_type_node.name))
            return

    if not isinstance(attribute_type_node, TypeInfo):
        # Unable to determine the attribute type.
        print("Unable to determine the attribute type")
        return

    context.cls.info = transform_type_info(
        context,
        proto_type_node,
        attribute_type_node,
        init)

    typeInfoByProtoTypeName[proto_type_node.fullname] = context.cls.info


def transform_type_info(
        context: mypy.plugin.ClassDefContext,
        proto_type_node: TypeInfo,
        attribute_type_node: TypeInfo,
        init: bool) -> TypeInfo:

    transformed_info: TypeInfo = context.cls.info

    # Get the list of proto_type class members that are not dunders or private
    names = [
        name for name in proto_type_node.names
        if not name.startswith('_')]

    transformedNames = []

    for name in names:
        proto_node = proto_type_node.names[name] # SymbolTableNode

        if isinstance(proto_node.node, FuncDef):
            # Ignore methods
            continue

        transformedNames.append(name)
        copied_node = proto_node.copy() # SymbolTableNode
        copied_node.node = copy.copy(proto_node.node) # Var

        copied_node.node._fullname = "{}.{}".format(
            transformed_info.fullname,
            copied_node.node.name)

        copied_node.plugin_generated = True

        try:
            nestedTypeInfo = typeInfoByProtoTypeName.get(
                proto_node.node.type.type.fullname,
                None)
        except AttributeError:
            nestedTypeInfo = None
            if isinstance(proto_node.node.type, mypy.types.AnyType):
                # AnyType is not a transformable class anyway.
                pass
            else:
                print(
                    "Warning: Failed to check fullname of {}: {}".format(
                        name,
                        proto_node.node.type))

        if nestedTypeInfo is not None:
            # This member's type has been transformed.
            copied_node.node.type = \
                mypy.types.Instance(nestedTypeInfo, [])
        else:
            if attribute_type_node.is_generic():
                typeArgs = [proto_node.node.type]
            else:
                typeArgs = []

            copied_node.node.type = \
                mypy.types.Instance(attribute_type_node, typeArgs)

        transformed_info.names[name] = copied_node

    protoTypeInstance = mypy.types.Instance(proto_type_node, [])

    if init:
        argument = Argument(
            Var(
                proto_type_node.name.lower(),
                protoTypeInstance),
            protoTypeInstance,
            None,
            ARG_POS)

        add_method_to_class(
            context.api,
            context.cls,
            "__init__",
            [argument, ],
            mypy.types.NoneType())

    add_method_to_class(
        context.api,
        context.cls,
        "GetProtoType",
        [],
        protoTypeInstance)

    # Now that the class is built, update the info
    for name in transformedNames:
        transformed_info.names[name].node.info = transformed_info

    return transformed_info

