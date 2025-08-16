"""Payment processor interface definitions."""

from __future__ import annotations

from typing import ClassVar, Set, Type


class ProcessorInterface:
    """Base processor interface supporting versioning.

    Subclasses may define available actions via the ``actions`` class attribute.
    When a processor exposes a ``connect`` action it must also implement a
    ``connect`` classmethod. The :meth:`versioned` classmethod enforces this
    contract.
    """

    actions: ClassVar[Set[str]] = set()

    @classmethod
    def versioned(cls) -> Type["ProcessorInterface"]:
        """Return a versioned interface for the processor.

        Processors declaring a ``connect`` action must implement a ``connect``
        classmethod. If absent, ``NotImplementedError`` is raised.
        """

        if "connect" in cls.actions and not hasattr(cls, "connect"):
            msg = "Processors with a 'connect' action must define a connect classmethod"
            raise NotImplementedError(msg)
        return cls
