/**
 * 工作流端口（handle）校验工具，与 nodetool web utils/handleUtils.ts 及后端 graph_utils.is_valid_edge 对齐。
 * 基于节点类型的 input_schema / output_schema（JSON Schema）判断端口是否存在。
 */

export type NodeTypeMetadata = {
  type: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
};

/** 从 JSON Schema 的 properties 提取键名（端口名） */
function getSchemaPropertyKeys(schema: Record<string, unknown> | undefined): string[] {
  const props = schema && typeof schema === 'object' && schema.properties;
  if (!props || typeof props !== 'object') return [];
  return Object.keys(props);
}

/** 获取节点类型的所有输出端口名 */
export function getOutputHandles(metadata: NodeTypeMetadata): string[] {
  return getSchemaPropertyKeys(metadata.output_schema);
}

/** 获取节点类型的所有输入端口名 */
export function getInputHandles(metadata: NodeTypeMetadata): string[] {
  return getSchemaPropertyKeys(metadata.input_schema);
}

/** 校验节点是否有指定名称的输出端口（与 nodetool hasOutputHandle 对齐）。无 schema 时放宽允许 */
export function hasOutputHandle(
  metadata: NodeTypeMetadata | undefined,
  handleName: string
): boolean {
  if (!handleName) return false;
  if (!metadata) return true; // 元数据未加载时放宽，与 nodetool 一致
  const names = getOutputHandles(metadata);
  if (names.length === 0) return true;
  return names.includes(handleName);
}

/** 校验节点是否有指定名称的输入端口（与 nodetool hasInputHandle 对齐）。无 schema 时放宽允许 */
export function hasInputHandle(
  metadata: NodeTypeMetadata | undefined,
  handleName: string
): boolean {
  if (!handleName) return false;
  if (!metadata) return true;
  const names = getInputHandles(metadata);
  if (names.length === 0) return true;
  return names.includes(handleName);
}

/**
 * 校验一条连接是否合法：源节点有 sourceHandle 输出，目标节点有 targetHandle 输入。
 * 用于 ReactFlow isValidConnection / onConnect 与后端 sanitize 行为一致。
 */
export function isValidConnection(
  sourceType: string,
  targetType: string,
  sourceHandle: string | null,
  targetHandle: string | null,
  typeMap: Map<string, NodeTypeMetadata>
): boolean {
  if (!sourceHandle || !targetHandle) return false;
  const sourceMeta = typeMap.get(sourceType);
  const targetMeta = typeMap.get(targetType);
  return (
    hasOutputHandle(sourceMeta, sourceHandle) &&
    hasInputHandle(targetMeta, targetHandle)
  );
}
