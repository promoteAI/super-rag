import asyncio
import copy
import time
import warnings
from typing import Any, Dict, Hashable, Iterable, List, Optional


class BaseNode:
    """
    Minimal synchronous node abstraction.

    Lifecycle:
    - prep(shared) -> prep_res
    - exec(prep_res) -> exec_res
    - post(shared, prep_res, exec_res) -> action (used for routing)
    """

    def __init__(self) -> None:
        self.params: Dict[str, Any] = {}
        # Mapping: action -> successor node
        self.successors: Dict[Hashable, "BaseNode"] = {}

    # ----- configuration -----
    def set_params(self, params: Dict[str, Any]) -> None:
        self.params = params

    def next(self, node: "BaseNode", action: Hashable = "default") -> "BaseNode":
        if action in self.successors:
            warnings.warn(f"Overwriting successor for action '{action}'", stacklevel=2)
        self.successors[action] = node
        return node

    # ----- overridable hooks -----
    def prep(self, shared: Dict[str, Any]) -> Any:  # pragma: no cover - framework default
        return None

    def exec(self, prep_res: Any) -> Any:  # pragma: no cover - framework default
        return None

    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Hashable:  # pragma: no cover
        # Default: always go through "default" edge
        return "default"

    # ----- internal helpers -----
    def _exec(self, prep_res: Any) -> Any:
        return self.exec(prep_res)

    def _run(self, shared: Dict[str, Any]) -> Hashable:
        prep_res = self.prep(shared)
        exec_res = self._exec(prep_res)
        return self.post(shared, prep_res, exec_res)

    # ----- public API -----
    def run(self, shared: Dict[str, Any]) -> Hashable:
        """
        Run this node in isolation. If it has successors, warn because
        flow orchestration should be done via `Flow`.
        """
        if self.successors:
            warnings.warn("Node has successors but `run()` does not traverse them. Use `Flow`.", stacklevel=2)
        return self._run(shared)

    # Fluent composition helpers: n1 >> n2, n1 - "ok" >> n2
    def __rshift__(self, other: "BaseNode") -> "BaseNode":
        return self.next(other)

    def __sub__(self, action: Hashable) -> "_ConditionalTransition":
        if isinstance(action, str):
            return _ConditionalTransition(self, action)
        raise TypeError("Action must be a string")


class _ConditionalTransition:
    """
    Helper to build conditional transitions with a fluent API:

        node - "ok" >> next_node
    """

    def __init__(self, src: BaseNode, action: Hashable):
        self.src = src
        self.action = action

    def __rshift__(self, tgt: BaseNode) -> BaseNode:
        return self.src.next(tgt, self.action)


class Node(BaseNode):
    """
    Synchronous node with simple retry & backoff support.
    """

    def __init__(self, max_retries: int = 1, wait: float = 0) -> None:
        super().__init__()
        self.max_retries = max_retries
        self.wait = wait
        self.cur_retry: int = 0

    def exec_fallback(self, prep_res: Any, exc: Exception) -> Any:  # pragma: no cover - override when needed
        raise exc

    def _exec(self, prep_res: Any) -> Any:
        for self.cur_retry in range(self.max_retries):
            try:
                return self.exec(prep_res)
            except Exception as e:  # pragma: no cover - behaviour depends on subclass
                if self.cur_retry == self.max_retries - 1:
                    return self.exec_fallback(prep_res, e)
                if self.wait > 0:
                    time.sleep(self.wait)


class BatchNode(Node):
    """
    Node that processes a batch of independent items sequentially.
    """

    def _exec(self, items: Optional[Iterable[Any]]) -> List[Any]:
        items = list(items or [])
        return [super(BatchNode, self)._exec(item) for item in items]


class Flow(BaseNode):
    """
    Synchronous flow orchestrator over linked nodes.

    Usage:
        f = Flow()
        start = f.start(MyStartNode())
        start >> middle - "retry" >> middle_again >> end
        result_action = f.run(shared)
    """

    def __init__(self, start: Optional[BaseNode] = None) -> None:
        super().__init__()
        self.start_node: Optional[BaseNode] = start

    # configuration
    def start(self, start: BaseNode) -> BaseNode:
        self.start_node = start
        return start

    # routing
    def get_next_node(self, curr: BaseNode, action: Hashable) -> Optional[BaseNode]:
        nxt = curr.successors.get(action or "default")
        if not nxt and curr.successors:
            warnings.warn(
                f"Flow ends: action '{action}' not found in {list(curr.successors.keys())}",
                stacklevel=2,
            )
        return nxt

    # orchestration
    def _orch(self, shared: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Hashable:
        if self.start_node is None:
            raise RuntimeError("Flow has no start node configured")

        current: Optional[BaseNode] = copy.copy(self.start_node)
        p: Dict[str, Any] = params or {**self.params}
        last_action: Hashable = None

        while current is not None:
            current.set_params(p)
            last_action = current._run(shared)
            next_node = self.get_next_node(current, last_action)
            current = copy.copy(next_node) if next_node is not None else None

        return last_action

    def _run(self, shared: Dict[str, Any]) -> Hashable:
        prep_res = self.prep(shared)
        orchestration_result = self._orch(shared)
        return self.post(shared, prep_res, orchestration_result)

    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Hashable:  # type: ignore[override]
        # Default: just propagate the last action
        return exec_res


class BatchFlow(Flow):
    """
    Flow that executes the same graph for a batch of parameter dicts.
    """

    def _run(self, shared: Dict[str, Any]) -> Any:
        prep_res = self.prep(shared) or []
        for params in prep_res:
            self._orch(shared, {**self.params, **params})
        return self.post(shared, prep_res, None)


class AsyncNode(Node):
    """
    Asynchronous node with retry & backoff support.
    Override the *_async methods to implement async behaviour.
    """

    async def prep_async(self, shared: Dict[str, Any]) -> Any:  # pragma: no cover - framework default
        return None

    async def exec_async(self, prep_res: Any) -> Any:  # pragma: no cover - framework default
        return None

    async def exec_fallback_async(self, prep_res: Any, exc: Exception) -> Any:  # pragma: no cover
        raise exc

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Hashable:  # pragma: no cover
        return "default"

    async def _exec(self, prep_res: Any) -> Any:  # type: ignore[override]
        for self.cur_retry in range(self.max_retries):
            try:
                return await self.exec_async(prep_res)
            except Exception as e:  # pragma: no cover - behaviour depends on subclass
                if self.cur_retry == self.max_retries - 1:
                    return await self.exec_fallback_async(prep_res, e)
                if self.wait > 0:
                    await asyncio.sleep(self.wait)

    async def run_async(self, shared: Dict[str, Any]) -> Hashable:
        if self.successors:
            warnings.warn(
                "Node has successors but `run_async()` does not traverse them. Use `AsyncFlow`.",
                stacklevel=2,
            )
        return await self._run_async(shared)

    async def _run_async(self, shared: Dict[str, Any]) -> Hashable:
        prep_res = await self.prep_async(shared)
        exec_res = await self._exec(prep_res)
        return await self.post_async(shared, prep_res, exec_res)

    def _run(self, shared: Dict[str, Any]) -> Hashable:  # pragma: no cover - guard against misuse
        raise RuntimeError("Use `run_async()` for AsyncNode and AsyncFlow.")


class AsyncBatchNode(AsyncNode, BatchNode):
    async def _exec(self, items: Optional[Iterable[Any]]) -> List[Any]:  # type: ignore[override]
        items = list(items or [])
        results: List[Any] = []
        for item in items:
            results.append(await super(AsyncBatchNode, self)._exec(item))
        return results


class AsyncParallelBatchNode(AsyncNode, BatchNode):
    async def _exec(self, items: Optional[Iterable[Any]]) -> List[Any]:  # type: ignore[override]
        items = list(items or [])
        return await asyncio.gather(*(super(AsyncParallelBatchNode, self)._exec(item) for item in items))


class AsyncFlow(Flow, AsyncNode):
    """
    Asynchronous version of `Flow`. Nodes can be either sync (`BaseNode`)
    or async (`AsyncNode`); async nodes are awaited, sync ones are executed directly.
    """

    async def _orch_async(self, shared: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Hashable:
        if self.start_node is None:
            raise RuntimeError("Flow has no start node configured")

        current: Optional[BaseNode] = copy.copy(self.start_node)
        p: Dict[str, Any] = params or {**self.params}
        last_action: Hashable = None

        while current is not None:
            current.set_params(p)
            if isinstance(current, AsyncNode):
                last_action = await current._run_async(shared)
            else:
                last_action = current._run(shared)
            next_node = self.get_next_node(current, last_action)
            current = copy.copy(next_node) if next_node is not None else None

        return last_action

    async def _run_async(self, shared: Dict[str, Any]) -> Hashable:
        prep_res = await self.prep_async(shared)
        orchestration_result = await self._orch_async(shared)
        return await self.post_async(shared, prep_res, orchestration_result)

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Hashable:  # type: ignore[override]
        return exec_res


class AsyncBatchFlow(AsyncFlow, BatchFlow):
    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        prep_res = await self.prep_async(shared) or []
        for params in prep_res:
            await self._orch_async(shared, {**self.params, **params})
        return await self.post_async(shared, prep_res, None)


class AsyncParallelBatchFlow(AsyncFlow, BatchFlow):
    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        prep_res = await self.prep_async(shared) or []
        await asyncio.gather(
            *(self._orch_async(shared, {**self.params, **params}) for params in prep_res),
        )
        return await self.post_async(shared, prep_res, None)

