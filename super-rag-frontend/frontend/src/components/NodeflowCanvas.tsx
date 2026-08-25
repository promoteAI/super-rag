import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Plus,
  LayoutGrid,
  Save,
  Zap,
  MoreVertical,
  Square,
  Play,
  Search,
  X,
  Download,
  Power,
  PencilLine,
  Copy,
  Trash2,
  Info,
} from 'lucide-react';
import { nodeflowApi, type NodeflowNodeType } from '../api/client';
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  type Connection,
  addEdge,
  useNodesState,
  useEdgesState,
  type NodeProps,
  type EdgeProps,
  Position,
  Handle,
  getBezierPath,
  BaseEdge,
  EdgeLabelRenderer,
  useReactFlow,
  type OnSelectionChangeParams,
} from 'reactflow';
import { isValidConnection as isValidConnectionCheck } from '../utils/workflowHandles';
import type { NodeTypeMetadata } from '../utils/workflowHandles';
import 'reactflow/dist/style.css';
import '../pages/WorkflowEditorPage.css';
import { cn, editorClassNames, stopPropagationHandlers } from './editor_ui';

export type NodeflowSelection = {
  id: string;
  label?: string;
  type?: string;
};

type ImageNodeData = {
  label: string;
};

type EditNodeData = {
  title: string;
};

type AgentNodeData = {
  name: string;
  subtitle?: string;
  /** 后端节点类型，保存到 workflow graph 时使用（start、vector_search、llm 等） */
  nodeType?: string;
  modelLabel?: string;
  prompt?: string;
  tools?: string[];
  inputs?: string[];
  outputs?: string[];
  details?: { label: string; value: string }[];
  moreDetails?: { label: string; value: string }[];
  /** 各端口当前值（来自 node.data），未连接时作为默认值展示 */
  fieldValues?: Record<string, unknown>;
  /** 已有连线接入的输入端口名，这些端口不展示默认值输入框而显示「已连接」 */
  connectedInputs?: string[];
};

type GenericNodeData = {
  title: string;
  subtitle?: string;
  /** 后端节点类型 */
  nodeType?: string;
};

export type WorkflowNodeData = ImageNodeData | EditNodeData | AgentNodeData | GenericNodeData;

type NodeflowCanvasProps = {
  onSelectionChange?: (node: NodeflowSelection | null) => void;
  /**
   * 当前在右侧 Inspector 中选中的节点 id，
   * 用于驱动画布中的节点名称更新。
   */
  selectedNodeId?: string | null;
  /**
   * 右侧 Inspector 中正在编辑的 label 文本，
   * 会同步映射到不同类型节点的数据字段上。
   */
  selectedLabel?: string;
  nodes?: Node<WorkflowNodeData>[];
  edges?: Edge[];
  onRunFlow?: () => void;
  /** 点击保存时回调，传入当前画布的 nodes 和 edges，由父组件调用 PUT /workflows/{id} 保存 */
  onSave?: (nodes: Node<WorkflowNodeData>[], edges: Edge[]) => void;
  /** 节点类型元数据（用于连接校验，与 nodetool hasInputHandle/hasOutputHandle 对齐）。不传则用画布内部加载的列表 */
  nodeTypeMetadata?: NodeflowNodeType[];
};

function ImageNode({ data }: NodeProps<WorkflowNodeData>) {
  const imageData = data as ImageNodeData;

  return (
    <div className="nf-node nf-node-image">
      <div className="nf-node-header-row">
        <div className="nf-node-title">Image</div>
        <div className="nf-node-subtitle">{imageData.label}</div>
      </div>
      <div className="nf-node-image-preview" />
      <Handle type="source" position={Position.Right} className="nf-handle nf-handle-right" />
    </div>
  );
}

function EditNode({ data }: NodeProps<WorkflowNodeData>) {
  const editData = data as EditNodeData;

  return (
    <div className="nf-node nf-node-edit">
      <Handle type="target" position={Position.Left} id="image-a" className="nf-handle nf-handle-left" />
      <Handle
        type="target"
        position={Position.Left}
        id="image-b"
        className="nf-handle nf-handle-left nf-handle-left-lower"
      />
      <Handle type="source" position={Position.Right} id="result" className="nf-handle nf-handle-right" />

      <div className="nf-node-header">
        <div className="nf-node-pill">Nodeflow · Image Edit</div>
        <h2 className="nf-node-title-large">{editData.title}</h2>
      </div>

      <div className="nf-node-fields">
        <div className="nf-field">
          <label className="nf-field-label">Prompt</label>
          <input
            className={cn('nf-field-input', editorClassNames.nodrag)}
            defaultValue="a man"
            {...stopPropagationHandlers}
          />
        </div>
        <div className="nf-field-grid">
          <div className="nf-field">
            <label className="nf-field-label">Image Input</label>
            <select className={cn('nf-field-input', editorClassNames.nodrag)} {...stopPropagationHandlers}>
              <option>Top Image</option>
              <option>Bottom Image</option>
            </select>
          </div>
          <div className="nf-field">
            <label className="nf-field-label">Image Size</label>
            <select className={cn('nf-field-input', editorClassNames.nodrag)} {...stopPropagationHandlers}>
              <option>1:1</option>
              <option>3:4</option>
              <option>16:9</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}

/** 将端口名转为展示标签（如 start_page -> Start Page） */
function portLabel(key: string): string {
  if (key === '—') return key;
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** 根据端口名/类型返回端口颜色类（与参考图一致：蓝/橙/紫/黄） */
function portColorClass(portKey: string): 'nf-port-blue' | 'nf-port-orange' | 'nf-port-purple' | 'nf-port-yellow' {
  const k = portKey.toLowerCase();
  if (k.includes('image') || k.includes('img')) return 'nf-port-purple';
  if (k.includes('text') || k.includes('prompt') || k.includes('chunk') || k.includes('content')) return 'nf-port-orange';
  if (k.includes('model')) return 'nf-port-yellow';
  return 'nf-port-blue';
}

function AgentNode({ id: nodeId, data, selected }: NodeProps<WorkflowNodeData>) {
  const agentData = data as AgentNodeData;
  const { setNodes } = useReactFlow();
  const [promptFocused, setPromptFocused] = useState(false);
  const hasPrompt = Boolean(agentData.prompt);
  const tools = agentData.tools ?? [];
  const inputs = (agentData.inputs ?? []).filter((k) => k !== '—');
  const outputs = (agentData.outputs ?? []).filter((k) => k !== '—');
  const details = agentData.details ?? [];
  const moreDetails = agentData.moreDetails ?? [];
  const fieldValues = agentData.fieldValues ?? {};
  const connectedInputs = new Set(agentData.connectedInputs ?? []);

  const handleFieldValueChange = useCallback(
    (portKey: string, value: string) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? {
                ...n,
                data: {
                  ...n.data,
                  fieldValues: {
                    ...((n.data as AgentNodeData).fieldValues ?? {}),
                    [portKey]: value,
                  },
                },
              }
            : n
        )
      );
    },
    [nodeId, setNodes]
  );

  return (
    <div className={cn('nf-node', 'nf-node-agent', selected && 'nf-node-selected')}>
      {selected && (
        <div className="nf-agent-toolbar" {...stopPropagationHandlers}>
          <button type="button" className="nf-agent-toolbar-btn" aria-label="Power">
            <Power size={12} />
          </button>
          <button type="button" className="nf-agent-toolbar-btn" aria-label="Edit">
            <PencilLine size={12} />
          </button>
          <button type="button" className="nf-agent-toolbar-btn" aria-label="Duplicate">
            <Copy size={12} />
          </button>
          <button type="button" className="nf-agent-toolbar-btn" aria-label="Delete">
            <Trash2 size={12} />
          </button>
          <button type="button" className="nf-agent-toolbar-btn" aria-label="Info">
            <Info size={12} />
          </button>
        </div>
      )}

      <div className="nf-agent-header">
        <div className="nf-agent-header-main">
          <div className="nf-agent-header-icon">”</div>
          <div className="nf-agent-title">{agentData.name || 'Node'}</div>
        </div>
      </div>
      {agentData.subtitle && (
        <div className="nf-agent-subtitle">{agentData.subtitle}</div>
      )}

      <div className="nf-node-fields nf-agent-fields">
        {hasPrompt && (
          <div className="nf-field nf-agent-section">
            <span className="nf-agent-section-strip nf-agent-strip-yellow" />
            <label className="nf-field-label">Prompt</label>
            <textarea
              className={cn(
                'nf-field-input',
                'nf-agent-textarea',
                editorClassNames.nodrag,
                promptFocused && editorClassNames.nowheel,
              )}
              defaultValue={agentData.prompt}
              rows={3}
              readOnly
              onFocus={() => setPromptFocused(true)}
              onBlur={() => setPromptFocused(false)}
              {...stopPropagationHandlers}
            />
          </div>
        )}

        {(tools.length > 0 || details.length > 0) && (
          <div className="nf-field nf-agent-section nf-agent-tools">
            <span className="nf-agent-section-strip nf-agent-strip-purple" />
            <label className="nf-field-label">{tools.length > 0 ? 'Tools' : 'Details'}</label>
            <div className="nf-agent-tools-row">
              <div className="nf-agent-tools-chips">
                {tools.length > 0
                  ? tools.map((tool) => (
                      <span key={tool} className="nf-agent-chip">
                        {tool}
                      </span>
                    ))
                  : details.slice(0, 3).map((item) => (
                      <span key={item.label} className="nf-agent-chip">
                        {item.label}
                      </span>
                    ))}
              </div>
              {tools.length > 0 && (
                <button type="button" className="nf-agent-tools-button" {...stopPropagationHandlers}>
                  + TOOLS
                </button>
              )}
            </div>
            {details.length > 0 && (
              <div className="nf-agent-details">
                {details.map((item) => (
                  <div key={item.label} className="nf-agent-detail-row">
                    <span className="nf-agent-detail-label">{item.label}</span>
                    <span className="nf-agent-detail-value">{item.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 每个输入端口一行：[彩色小方块] [字段名] [默认值/已连接] */}
        {inputs.length > 0 && (
          <div className="nf-agent-io-section">
            {inputs.map((portKey) => (
              <div key={portKey} className="nf-field-row nf-field-row-input">
                <div className={cn('nf-port-wrap', portColorClass(portKey))}>
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={portKey}
                    className="nf-handle nf-handle-left"
                  />
                </div>
                <label className="nf-field-label nf-field-row-label">{portLabel(portKey)}</label>
                {connectedInputs.has(portKey) ? (
                  <span className="nf-field-connected">已连接</span>
                ) : (
                  <input
                    type="text"
                    className={cn('nf-field-input nf-field-row-value', editorClassNames.nodrag)}
                    value={fieldValues[portKey] != null ? String(fieldValues[portKey]) : ''}
                    onChange={(e) => handleFieldValueChange(portKey, e.target.value)}
                    placeholder="默认值"
                    {...stopPropagationHandlers}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* 每个输出端口一行：[字段名] [彩色小方块] */}
        {outputs.length > 0 && (
          <div className="nf-agent-io-section nf-agent-outputs">
            {outputs.map((portKey) => (
              <div key={portKey} className="nf-field-row nf-field-row-output">
                <label className="nf-field-label nf-field-row-label">{portLabel(portKey)}</label>
                <div className={cn('nf-port-wrap', portColorClass(portKey))}>
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={portKey}
                    className="nf-handle nf-handle-right"
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {moreDetails.length > 0 && (
          <>
            <button type="button" className="nf-agent-more-row" {...stopPropagationHandlers}>
              <span className="nf-agent-more-chevron">▾</span>
              <span className="nf-agent-more-label">More</span>
            </button>
            <div className="nf-agent-bottom-row">
              <button type="button" className="nf-agent-tools-bottom-button" {...stopPropagationHandlers}>
                DETAILS
              </button>
              <div className="nf-agent-bottom-tags">
                {moreDetails.slice(0, 4).map((item) => (
                  <span key={item.label} className="nf-agent-bottom-tag">
                    {item.label}
                  </span>
                ))}
              </div>
            </div>
            <div className="nf-agent-more-details">
              {moreDetails.map((item) => (
                <div key={item.label} className="nf-agent-detail-row">
                  <span className="nf-agent-detail-label">{item.label}</span>
                  <span className="nf-agent-detail-value">{item.value}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/** 自定义边：点击选中时在连线中点显示删除 x，可删除连线 */
function DeletableEdge({ id, selected, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition }: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });
  const { setEdges } = useReactFlow();

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEdges((edges) => edges.filter((edge) => edge.id !== id));
  };

  return (
    <>
      <BaseEdge id={id} path={edgePath} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
        >
          {selected && (
            <button
              type="button"
              className="nf-edge-delete-btn"
              onClick={handleDelete}
              aria-label="Delete edge"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const edgeTypes = {
  default: DeletableEdge,
};

const nodeTypes = {
  image: ImageNode,
  edit: EditNode,
  agent: AgentNode,
  generic: GenericNode,
};

const initialNodes: Node<WorkflowNodeData>[] = [];

const initialEdges: Edge[] = [];

function GenericNode({ data }: NodeProps<WorkflowNodeData>) {
  const nodeData = data as GenericNodeData;

  return (
    <div className="nf-node">
      <Handle type="target" position={Position.Left} className="nf-handle nf-handle-left" />
      <Handle type="source" position={Position.Right} className="nf-handle nf-handle-right" />
      <div className="nf-node-header-row">
        <div className="nf-node-title">{nodeData.title}</div>
        {nodeData.subtitle && <div className="nf-node-subtitle">{nodeData.subtitle}</div>}
      </div>
    </div>
  );
}

export function NodeflowCanvas({
  onSelectionChange,
  selectedNodeId,
  selectedLabel,
  nodes: externalNodes,
  edges: externalEdges,
  onRunFlow,
  onSave,
  nodeTypeMetadata,
}: NodeflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>(externalNodes ?? initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(externalEdges ?? initialEdges);
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const [nodePaletteOpen, setNodePaletteOpen] = useState(false);
  const [nodeSearch, setNodeSearch] = useState('');
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement>(null);
  const [installedNodeTypes, setInstalledNodeTypes] = useState<NodeflowNodeType[]>([]);
  const [paletteCategory, setPaletteCategory] = useState<string>('All');

  useEffect(() => {
    if (!nodePaletteOpen) return;
    nodeflowApi
      .listNodeTypes()
      .then((res) => setInstalledNodeTypes(res.node_types))
      .catch(() => setInstalledNodeTypes([]));
  }, [nodePaletteOpen]);

  // 首次挂载加载节点类型，供连接校验使用（与 nodetool 一致）
  useEffect(() => {
    nodeflowApi
      .listNodeTypes()
      .then((res) => setInstalledNodeTypes((prev) => (prev.length ? prev : res.node_types)))
      .catch(() => {});
  }, []);

  const typeMap = useMemo(() => {
    const list = nodeTypeMetadata ?? installedNodeTypes;
    return new Map<string, NodeTypeMetadata>(list.map((t) => [t.type, t]));
  }, [nodeTypeMetadata, installedNodeTypes]);

  const isValidConnectionCallback = useCallback(
    (connection: Connection) => {
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);
      const sourceType = (sourceNode?.data as AgentNodeData)?.nodeType;
      const targetType = (targetNode?.data as AgentNodeData)?.nodeType;
      if (!sourceType || !targetType) return false;
      return isValidConnectionCheck(
        sourceType,
        targetType,
        connection.sourceHandle ?? null,
        connection.targetHandle ?? null,
        typeMap
      );
    },
    [nodes, typeMap]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!isValidConnectionCallback(connection)) return;
      setEdges((eds) => addEdge({ ...connection, animated: true }, eds));
    },
    [setEdges, isValidConnectionCallback]
  );

  useEffect(() => {
    if (externalNodes) {
      setNodes(externalNodes);
    }
  }, [externalNodes, setNodes]);

  useEffect(() => {
    if (externalEdges) {
      setEdges(externalEdges);
    }
  }, [externalEdges, setEdges]);

  const handleSelectionChange = useCallback(
    (params: OnSelectionChangeParams) => {
      const selected = params.nodes?.[0] as Node<WorkflowNodeData> | undefined;
      const newIds = new Set((params.nodes ?? []).map((n) => n.id));
      setSelectedNodeIds(newIds);

      if (selected && onSelectionChange) {
        let label: string | undefined;
        if (selected.type === 'image') {
          label = (selected.data as ImageNodeData).label;
        } else if (selected.type === 'edit') {
          label = (selected.data as EditNodeData).title;
        } else if (selected.type === 'agent') {
          label = (selected.data as AgentNodeData).name;
        } else if (selected.type === 'generic') {
          label = (selected.data as GenericNodeData).title;
        }
        onSelectionChange({
          id: selected.id,
          label,
          type: selected.type,
        });
      } else if (onSelectionChange) {
        onSelectionChange(null);
      }
    },
    [onSelectionChange],
  );

  const handleKeyDown: React.KeyboardEventHandler<HTMLDivElement> = useCallback(
    (event) => {
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNodeIds.size > 0) {
        event.preventDefault();
        const ids = new Set(selectedNodeIds);
        setNodes((nds) => nds.filter((n) => !ids.has(n.id)));
        setEdges((eds) => eds.filter((e) => !ids.has(e.source) && !ids.has(e.target)));
        if (onSelectionChange) {
          onSelectionChange(null);
        }
      }
    },
    [selectedNodeIds, setNodes, setEdges, onSelectionChange],
  );

  /** 从 JSON Schema 的 properties 提取键名，用于 inputs/outputs/details */
  const getSchemaKeys = useCallback((schema: Record<string, unknown> | undefined): string[] => {
    const props = schema && typeof schema === 'object' && schema.properties;
    if (!props || typeof props !== 'object') return [];
    return Object.keys(props);
  }, []);

  const addNode = useCallback(
    (nodeType: NodeflowNodeType) => {
      const backendType = nodeType.type;
      const newId = `${backendType}-${Date.now().toString(36)}`;
      const position = { x: 360 + Math.random() * 120, y: 60 + Math.random() * 220 };

      const inputKeys = getSchemaKeys(nodeType.input_schema as Record<string, unknown> | undefined);
      const outputKeys = getSchemaKeys(nodeType.output_schema as Record<string, unknown> | undefined);
      const isLlm = backendType === 'llm';

      // 所有节点类型都展开渲染：用 schema 生成 inputs/outputs，用 details/moreDetails 区分类型
      const details: { label: string; value: string }[] = isLlm
        ? [
            { label: 'type', value: backendType },
            { label: 'temperature', value: '0.7' },
          ]
        : inputKeys.slice(0, 3).map((k) => ({ label: k, value: '—' }));

      const moreDetails: { label: string; value: string }[] = isLlm
        ? [
            { label: 'model', value: '—' },
            { label: 'max_tokens', value: '—' },
          ]
        : inputKeys.slice(3, 6).map((k) => ({ label: k, value: '—' }));

      // 无 schema 时保留占位，保证区块仍显示
      const inputs = inputKeys.length > 0 ? inputKeys : ['—'];
      const outputs = outputKeys.length > 0 ? outputKeys : ['—'];
      if (details.length === 0) details.push({ label: 'type', value: backendType });

      const agentData: AgentNodeData = {
        name: nodeType.label,
        subtitle: backendType,
        nodeType: backendType,
        prompt: isLlm ? ' ' : '', // 仅 LLM 显示 Prompt 占位
        details,
        moreDetails,
        inputs,
        outputs,
      };

      setNodes((nds) => [
        ...nds,
        {
          id: newId,
          type: 'agent',
          position,
          data: agentData,
        } as Node<WorkflowNodeData>,
      ]);
      setNodePaletteOpen(false);
      setNodeSearch('');
    },
    [setNodes, getSchemaKeys],
  );

  const handleDownloadJson = useCallback(() => {
    const graphNodes = nodes.map((node) => {
      const ui_properties: Record<string, unknown> = {
        position: node.position,
        zIndex: node.zIndex ?? 0,
        width: node.style?.width ?? undefined,
        height: node.style?.height ?? undefined,
        selectable: node.selectable !== false,
        bypassed: false,
      };
      return {
        id: node.id,
        type: node.type || 'agent',
        data: node.data ?? {},
        ui_properties,
      };
    });
    const graphEdges = edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      ...(edge.sourceHandle && { sourceHandle: edge.sourceHandle }),
      ...(edge.targetHandle && { targetHandle: edge.targetHandle }),
    }));
    const payload = {
      graph: {
        nodes: graphNodes,
        edges: graphEdges,
      },
      exportedAt: new Date().toISOString(),
    };
    const json = JSON.stringify(payload, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setMoreMenuOpen(false);
  }, [nodes, edges]);

  useEffect(() => {
    if (!moreMenuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target instanceof HTMLElement ? e.target : null;
      if (moreMenuRef.current && target && !moreMenuRef.current.contains(target)) {
        setMoreMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [moreMenuOpen]);

  // 根据右侧 Inspector 的输入，实时更新当前选中节点的名称。
  useEffect(() => {
    if (!selectedNodeId) return;
    if (typeof selectedLabel !== 'string') return;

    setNodes((nds) =>
      nds.map((n) => {
        if (n.id !== selectedNodeId) return n;

        if (n.type === 'image') {
          return { ...n, data: { ...(n.data as ImageNodeData), label: selectedLabel } };
        }
        if (n.type === 'edit') {
          return { ...n, data: { ...(n.data as EditNodeData), title: selectedLabel } };
        }
        if (n.type === 'agent') {
          return { ...n, data: { ...(n.data as AgentNodeData), name: selectedLabel } };
        }
        if (n.type === 'generic') {
          return { ...n, data: { ...(n.data as GenericNodeData), title: selectedLabel } };
        }
        return n;
      }),
    );
  }, [selectedNodeId, selectedLabel, setNodes]);

  return (
    <div
      className="workflow-canvas"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnectionCallback}
        onSelectionChange={handleSelectionChange}
        fitView
        proOptions={{ hideAttribution: true }}
        edgesFocusable
      >
        <Controls className="workflow-controls" />
        <Background gap={20} size={1} color="rgba(0,0,0,0.06)" />
      </ReactFlow>

      {nodePaletteOpen && (
        <div
          className="workflow-node-palette-backdrop"
          onClick={() => setNodePaletteOpen(false)}
        >
          <div
            className="workflow-node-palette"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="workflow-node-palette-header">
              <div className="workflow-node-palette-search">
                <Search size={16} className="workflow-node-palette-search-icon" />
                <input
                  type="text"
                  className="workflow-node-palette-search-input"
                  placeholder="Search for nodes..."
                  value={nodeSearch}
                  onChange={(event) => setNodeSearch(event.target.value)}
                />
              </div>
              <button
                type="button"
                className="workflow-node-palette-close"
                onClick={() => setNodePaletteOpen(false)}
                aria-label="Close node palette"
              >
                <X size={16} />
              </button>
            </div>

            {(() => {
              const categories = Array.from(
                new Set(['All', ...installedNodeTypes.map((t) => t.category || 'Other')]),
              );
              const filtered = installedNodeTypes.filter((nt) => {
                const matchSearch = !nodeSearch || [nt.type, nt.label, nt.category].some(
                  (s) => s && s.toLowerCase().includes(nodeSearch.toLowerCase()),
                );
                const matchCategory =
                  paletteCategory === 'All' || (nt.category || 'Other') === paletteCategory;
                return matchSearch && matchCategory;
              });
              return (
                <>
                  <div className="workflow-node-palette-types">
                    {categories.map((cat) => (
                      <button
                        key={cat}
                        type="button"
                        className={`palette-type-chip ${paletteCategory === cat ? 'active' : ''}`}
                        onClick={() => setPaletteCategory(cat)}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>

                  <div className="workflow-node-palette-body">
                    <div className="workflow-node-palette-sidebar">
                      <button
                        type="button"
                        className={`palette-sidebar-item ${paletteCategory === 'All' ? 'active' : ''}`}
                        onClick={() => setPaletteCategory('All')}
                      >
                        已安装节点
                      </button>
                    </div>

                    <div className="workflow-node-palette-grid">
                      {filtered.map((nt) => (
                        <button
                          key={nt.type}
                          type="button"
                          className="workflow-node-palette-card"
                          onClick={() => addNode(nt)}
                        >
                          <div className="palette-card-icon">
                            <Plus size={14} />
                          </div>
                          <div className="palette-card-text">
                            <div className="palette-card-title">{nt.label}</div>
                            <div className="palette-card-subtitle">
                              {nt.category && `${nt.category} · `}{nt.type}
                            </div>
                          </div>
                        </button>
                      ))}
                      {filtered.length === 0 && (
                        <div className="workflow-node-palette-empty">
                          {installedNodeTypes.length === 0
                            ? '加载中…'
                            : '无匹配节点'}
                        </div>
                      )}
                    </div>
                  </div>
                </>
              );
            })()}
          </div>
        </div>
      )}

      <div className="workflow-floating-toolbar">
        <button
          type="button"
          className="workflow-floating-btn workflow-floating-btn-primary"
          title="Add"
          onClick={() => setNodePaletteOpen(true)}
        >
          <Plus size={18} />
        </button>
        <button type="button" className="workflow-floating-btn" title="Auto Layout">
          <LayoutGrid size={18} />
        </button>
        <button
          type="button"
          className="workflow-floating-btn"
          title="Save"
          onClick={() => onSave?.(nodes, edges)}
        >
          <Save size={18} />
        </button>
        <button type="button" className="workflow-floating-btn" title="Instant Update">
          <Zap size={18} />
        </button>
        <div className="workflow-floating-more-wrap" ref={moreMenuRef}>
          <button
            type="button"
            className="workflow-floating-btn"
            title="More"
            aria-expanded={moreMenuOpen}
            aria-haspopup="true"
            onClick={() => setMoreMenuOpen((v) => !v)}
          >
            <MoreVertical size={18} />
          </button>
          {moreMenuOpen && (
            <div className="workflow-floating-more-menu" role="menu">
              <button
                type="button"
                className="workflow-floating-more-menu-item"
                role="menuitem"
                onClick={handleDownloadJson}
              >
                <Download size={14} />
                <span>Download JSON</span>
              </button>
            </div>
          )}
        </div>
        <span className="workflow-floating-divider" />
        <button type="button" className="workflow-floating-btn" title="Stop">
          <Square size={18} />
        </button>
        <button
          type="button"
          className="workflow-floating-btn workflow-floating-btn-run"
          title="Run"
          onClick={onRunFlow}
        >
          <Play size={18} />
        </button>
      </div>
    </div>
  );
}

export default NodeflowCanvas;

