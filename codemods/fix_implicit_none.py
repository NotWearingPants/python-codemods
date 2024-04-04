import libcst
from libcst.codemod import VisitorBasedCodemodCommand

def type_includes_none(type_expr: libcst.BaseExpression) -> bool:
	match type_expr:
		case libcst.Name(value='None'):
			return True

		case libcst.BinaryOperation(
			operator=libcst.BitOr(),
		):
			return type_includes_none(type_expr.left) or type_includes_none(type_expr.right)

		case libcst.Subscript(
			value=(
				libcst.Name(value='Optional')
				|
				libcst.Attribute(
					value=libcst.Name(value='typing'),
					attr=libcst.Name(value='Optional'),
				)
			),
		):
			return True

		case _:
			return False

class Run(VisitorBasedCodemodCommand):
	def leave_Param(
		self, original_node: libcst.Param, updated_node: libcst.Param
	) -> libcst.CSTNode:
		if updated_node.default is None:
			return updated_node
		if updated_node.annotation is None:
			return updated_node

		default_value_is_none = (
			isinstance(updated_node.default, libcst.Name)
			and
			updated_node.default.value == 'None'
		)
		annotation_includes_none = type_includes_none(updated_node.annotation.annotation)

		if default_value_is_none == annotation_includes_none:
			return updated_node

		if default_value_is_none:
			# add `None` to the type annotation
			return updated_node.with_changes(
				annotation=libcst.Annotation(
					annotation=libcst.BinaryOperation(
						left=updated_node.annotation.annotation,
						operator=libcst.BitOr(),
						right=libcst.Name(value='None'),
					),
				),
			)
		else:
			# remove `None` from the type annotation
			return updated_node.with_changes(
				annotation=updated_node.annotation.with_changes(
					# TODO: remove `None` here somehow, hopefully the annotation is a union or `Optional[T]`
					annotation=updated_node.annotation.annotation,
				),
			)
