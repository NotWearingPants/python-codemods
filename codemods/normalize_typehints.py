import libcst
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor
from libcst.metadata import Scope, ScopeProvider, scope_provider

# https://docs.python.org/3/library/typing.html#deprecated-aliases
# https://peps.python.org/pep-0585/
DEPRECATED_TYPES_REPLACEMENTS = {
	'typing.Dict': 'dict',
	'typing.List': 'list',
	'typing.Set': 'set',
	'typing.FrozenSet': 'frozenset',
	'typing.Tuple': 'tuple',
	'typing.Type': 'type',
	'typing.DefaultDict': 'collections.defaultdict',
	'typing.OrderedDict': 'collections.OrderedDict',
	'typing.ChainMap': 'collections.ChainMap',
	'typing.Counter': 'collections.Counter',
	'typing.Deque': 'collections.deque',
	'typing.Text': 'str',
	'typing.AbstractSet': 'collections.abc.Set',
	# TODO: which one is it?
	# 'typing.ByteString': 'collections.abc.Buffer' or 'collections.abc.ByteString' or 'bytes | bytearray | memoryview',
	'typing.Collection': 'collections.abc.Collection',
	'typing.Container': 'collections.abc.Container',
	'typing.ItemsView': 'collections.abc.ItemsView',
	'typing.KeysView': 'collections.abc.KeysView',
	'typing.Mapping': 'collections.abc.Mapping',
	'typing.MappingView': 'collections.abc.MappingView',
	'typing.MutableMapping': 'collections.abc.MutableMapping',
	'typing.MutableSequence': 'collections.abc.MutableSequence',
	'typing.MutableSet': 'collections.abc.MutableSet',
	'typing.Sequence': 'collections.abc.Sequence',
	'typing.ValuesView': 'collections.abc.ValuesView',
	'typing.Coroutine': 'collections.abc.Coroutine',
	'typing.AsyncGenerator': 'collections.abc.AsyncGenerator',
	'typing.AsyncIterable': 'collections.abc.AsyncIterable',
	'typing.AsyncIterator': 'collections.abc.AsyncIterator',
	'typing.Awaitable': 'collections.abc.Awaitable',
	'typing.Iterable': 'collections.abc.Iterable',
	'typing.Iterator': 'collections.abc.Iterator',
	'typing.Callable': 'collections.abc.Callable',
	'typing.Generator': 'collections.abc.Generator',
	'typing.Hashable': 'collections.abc.Hashable',
	'typing.Reversible': 'collections.abc.Reversible',
	'typing.Sized': 'collections.abc.Sized',
	'typing.ContextManager': 'contextlib.AbstractContextManager',
	'typing.AsyncContextManager': 'contextlib.AbstractAsyncContextManager',
	'typing.Pattern': 're.Pattern',
	'typing.re.Pattern': 're.Pattern',
	'typing.Match': 're.Match',
	'typing.re.Match': 're.Match',
}

def get_qualified_imported_name(scope: Scope, node: libcst.CSTNode) -> str | None:
	qualified_names = scope.get_qualified_names_for(node)

	# this ignores some imports (e.g. inside `try-except`),
	# they're harder to deal with but we probably don't care about them
	if len(qualified_names) != 1:
		return None

	qualified_name = next(iter(qualified_names))

	if qualified_name.source != scope_provider.QualifiedNameSource.IMPORT:
		return None

	return qualified_name.name

# TODO: implement https://github.com/Instagram/LibCST/issues/341#issuecomment-662156212
#       because `2 * Union[3, 4]` should become `2 * (3 + 4)` and not `2 * 3 + 4`.
#       currently the `T1 | (T2 | T3)` -> `T1 | T2 | T3` step is not necessary
#       since nested bin-ops never add parentheses, but we'll need it after implementing auto-parenthesis.
class Run(VisitorBasedCodemodCommand):
	DESCRIPTION = '''
		`Optional[T]` -> `T | None`
		`Union[T1, T2]` -> `T1 | T2`
		`T1 | (T2 | T3)` -> `T1 | T2 | T3`
		replaces deprecated types (e.g. `typing.List` -> `list`, `typing.Type` -> `type`)

		Doesn't remove imports that become unused (e.g. `from typing import Dict`).
	'''

	METADATA_DEPENDENCIES = (ScopeProvider,)

	def __init__(self, context: CodemodContext) -> None:
		super().__init__(context)
		self.inside_type_annotation = False

	def enter_Annotation(
		self, original_node: libcst.Annotation, updated_node: libcst.Annotation
	) -> libcst.CSTNode:
		self.inside_type_annotation = True
		return updated_node

	def leave_Annotation(
		self, original_node: libcst.Annotation, updated_node: libcst.Annotation
	) -> libcst.CSTNode:
		# annotations can't be nested
		self.inside_type_annotation = False
		return updated_node

	def leave_Subscript(
		self, original_node: libcst.Subscript, updated_node: libcst.Subscript
	) -> libcst.CSTNode:
		scope = self.get_metadata(ScopeProvider, original_node)

		# `Optional[T]` -> `T | None`
		match updated_node:
			case libcst.Subscript(
				value=(libcst.Name() | libcst.Attribute()) as type_reference,
				slice=(
					libcst.SubscriptElement(
						slice=libcst.Index(value),
					),
				),
			):
				if get_qualified_imported_name(scope, type_reference) == 'typing.Optional':
					return libcst.BinaryOperation(
						left=value,
						operator=libcst.BitOr(),
						right=libcst.Name(value='None'),
					)

		# `Union[T1, T2]` -> `T1 | T2`
		match updated_node:
			case libcst.Subscript(
				value=(libcst.Name() | libcst.Attribute()) as type_reference,
				slice=types,
			):
				if get_qualified_imported_name(scope, type_reference) == 'typing.Union':
					replacement = None

					for type in types:
						match type:
							case libcst.SubscriptElement(
								slice=libcst.Index(value),
							):
								replacement = libcst.BinaryOperation(
									left=replacement,
									operator=libcst.BitOr(),
									right=value,
								) if replacement else value

							case _:
								return updated_node

					return replacement

		return updated_node

	# TODO: only update if `self.inside_type_annotation` or in an expression
	#       that uses things from `typing` so they're probably type vars
	def leave_BinaryOperation(
		self, original_node: libcst.BinaryOperation, updated_node: libcst.BinaryOperation
	) -> libcst.CSTNode:
		# `T1 | (T2 | T3)` -> `T1 | T2 | T3`
		match updated_node:
			case libcst.BinaryOperation(
				left=t1,
				operator=libcst.BitOr(),
				right=libcst.BinaryOperation(
					left=t2,
					operator=libcst.BitOr(),
					right=t3,
				),
			):
				return libcst.BinaryOperation(
					left=libcst.BinaryOperation(
						left=t1,
						operator=libcst.BitOr(),
						right=t2,
					),
					operator=libcst.BitOr(),
					right=t3,
				)

		return updated_node

	def leave_Name(
		self, original_node: libcst.Name, updated_node: libcst.Name
	) -> libcst.CSTNode:
		return self.leave_Name_or_Attribute(original_node, updated_node)

	def leave_Attribute(
		self, original_node: libcst.Attribute, updated_node: libcst.Attribute
	) -> libcst.CSTNode:
		return self.leave_Name_or_Attribute(original_node, updated_node)

	def leave_Name_or_Attribute(
		self, original_node: libcst.Name | libcst.Attribute, updated_node: libcst.Name | libcst.Attribute
	) -> libcst.CSTNode:
		try:
			scope = self.get_metadata(ScopeProvider, original_node)
		except Exception:
			# we're inside an `import` statement
			return updated_node

		qualified_name = get_qualified_imported_name(scope, updated_node)
		if not qualified_name:
			return updated_node

		replacement_qualified_name = DEPRECATED_TYPES_REPLACEMENTS.get(qualified_name)
		if not replacement_qualified_name:
			return updated_node

		# TODO: reuse existing imports for part of the qualified name if possible,
		#       e.g. if we need `collections.abc.Container` and there's `from collections import abc` then use `abc.Container`
		replacement_module_name, _, replacement_name = replacement_qualified_name.rpartition('.')

		# for builtins this will be empty, otherwise we need to import
		if replacement_module_name:
			if self.inside_type_annotation:
				# TODO: add the import inside an `if TYPE_CHECKING` (and add the `if` if it doesn't exist)
				pass
			AddImportsVisitor.add_needed_import(self.context, replacement_module_name, replacement_name)

		return libcst.Name(replacement_name)
