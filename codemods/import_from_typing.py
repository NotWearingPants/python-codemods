import libcst
from libcst.codemod import VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor

class Run(VisitorBasedCodemodCommand):
	DESCRIPTION = '''
		Replace `import typing` with `from typing import ...`
	'''

	def leave_Import(
		self, original_node: libcst.Import, updated_node: libcst.Import
	) -> libcst.CSTNode:
		for name in original_node.names:
			if name.name.value == 'typing':
				return libcst.RemoveFromParent()

		return original_node

	def leave_Attribute(
		self, original_node: libcst.Attribute, updated_node: libcst.Attribute
	) -> libcst.CSTNode:
		match original_node:
			case libcst.Attribute(
				value=libcst.Name(value='typing'),
				attr=libcst.Name(value=value) as attr,
			):
				AddImportsVisitor.add_needed_import(self.context, 'typing', value)
				return attr

		return original_node
