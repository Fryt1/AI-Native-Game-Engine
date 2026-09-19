"""Read an Agent-authored Workflow from JSON, then check its structure.

Two layers, deliberately separate:

* ``schema.py`` checks the document's **shape and format** against
  ``templates/workflow.schema.json``, the code-defined spec;
* ``tree_validate.py`` checks the **semantics** the schema cannot express --
  sibling uniqueness, dependency order, which source a check may read.

``deserialize.py`` turns the document into model objects and decides nothing.
"""

from .deserialize import (
    WorkflowDeserializationError,
    acceptance_check_from_dict,
    check_result_from_dict,
    execution_item_result_from_dict,
    execution_result_from_dict,
    node_check_from_dict,
    node_from_dict,
    task_from_dict,
    workflow_from_dict,
)
from .tree_validate import (
    TreeIntegrityError,
    TreeIssue,
    validate_tree_structure,
)

__all__ = [
    "TreeIntegrityError",
    "TreeIssue",
    "WorkflowDeserializationError",
    "acceptance_check_from_dict",
    "check_result_from_dict",
    "execution_item_result_from_dict",
    "execution_result_from_dict",
    "node_check_from_dict",
    "node_from_dict",
    "task_from_dict",
    "validate_tree_structure",
    "workflow_from_dict",
]
