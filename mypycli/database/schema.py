from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Callable


def _wire_model(model: BaseModel, callback: Any) -> None:
    """Recursively set zero-arg ``_on_save`` on the model and its nested BaseModel fields."""
    object.__setattr__(model, "_on_save", callback)
    for field_name in type(model).model_fields:
        child = getattr(model, field_name, None)
        if isinstance(child, BaseModel):
            _wire_model(child, callback)


def _wire_patch(root: BaseModel, patch_cb: Callable[[str, Any], None]) -> None:
    """Wire ``root`` so field changes fire ``patch_cb(top_field, dumped_value)``."""
    object.__setattr__(root, "_on_patch", patch_cb)
    for field_name in type(root).model_fields:
        child = getattr(root, field_name, None)
        if isinstance(child, BaseModel):
            _wire_subtree_to_field(root, field_name, child, patch_cb)


def _wire_subtree_to_field(
    root: BaseModel,
    field_name: str,
    node: BaseModel,
    patch_cb: Callable[[str, Any], None],
) -> None:
    """Make every descendant BaseModel re-dump and patch ``root.<field_name>`` on change."""

    def _patch() -> None:
        patch_cb(field_name, root.model_dump(include={field_name})[field_name])

    stack: list[BaseModel] = [node]
    while stack:
        current = stack.pop()
        object.__setattr__(current, "_on_save", _patch)
        for fn in type(current).model_fields:
            value = getattr(current, fn, None)
            if isinstance(value, BaseModel):
                stack.append(value)


class DatabaseSchema(BaseModel):
    """Pydantic model where field assignment fires ``_on_patch`` (preferred) or ``_on_save``."""

    model_config = ConfigDict(validate_assignment=True, populate_by_name=True)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name.startswith("_"):
            return
        patch = getattr(self, "_on_patch", None)
        if patch is not None and name in type(self).model_fields:
            current = getattr(self, name)
            if isinstance(current, BaseModel):
                _wire_subtree_to_field(self, name, current, patch)
            patch(name, self.model_dump(include={name})[name])
            return
        cb = getattr(self, "_on_save", None)
        if cb is None:
            return
        if isinstance(value, BaseModel):
            _wire_model(value, cb)
        cb()
