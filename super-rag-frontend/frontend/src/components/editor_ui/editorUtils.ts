import type React from "react";

/**
 * Editor UI utilities for ReactFlow nodes.
 */

export const reactFlowClasses = {
  nodrag: "nodrag",
  nowheel: "nowheel",
  nopan: "nopan"
} as const;

export const editorClassNames = reactFlowClasses;

export const cn = (...classes: (string | false | null | undefined)[]): string =>
  classes.filter(Boolean).join(" ");

export const stopPropagationHandlers = {
  onMouseDown: (event: React.MouseEvent) => event.stopPropagation(),
  onPointerDown: (event: React.PointerEvent) => event.stopPropagation()
} as const;
