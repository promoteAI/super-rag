import { useEffect, useMemo, useState } from 'react';
import NodeflowCanvas, { type NodeflowSelection, type WorkflowNodeData } from '../components/NodeflowCanvas';
import WorkflowsPanel from '../components/WorkflowsPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { useLocation, useParams } from 'react-router-dom';
import { workflowsApi, nodeflowApi, type NodeflowNodeType } from '../api/client';
import type { WorkflowRecord, WorkflowGraph, WorkflowGraphEdge, WorkflowGraphNode } from '../types';
import type { Edge, Node } from 'reactflow';
import { EditorUiProvider } from '../components/editor_ui';
import './WorkflowEditorPage.css';

/** 从节点类型 API 的 JSON Schema 中取出 properties 键名，与拖入节点时一致 */
function getSchemaKeys(schema: Record<string, unknown> | undefined): string[] {
  const props = schema?.properties;
  if (!props || typeof props !== 'object') return [];
  return Object.keys(props);
}

export default function WorkflowEditorPage() {
  const [selection, setSelection] = useState<NodeflowSelection | null>(null);
  const [editingLabel, setEditingLabel] = useState('');
  const location = useLocation();
  const showPanel = new URLSearchParams(location.search).get('panel') === '1';
  const { id: workflowId } = useParams<{ id?: string }>();
  const [workflow, setWorkflow] = useState<WorkflowRecord | null>(null);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [nodeTypes, setNodeTypes] = useState<NodeflowNodeType[]>([]);

  useEffect(() => {
    nodeflowApi.listNodeTypes().then((r) => setNodeTypes(r.node_types)).catch(() => setNodeTypes([]));
  }, []);

  useEffect(() => {
    const loadWorkflow = async () => {
      if (!workflowId) {
        setWorkflow(null);
        setWorkflowError(null);
        return;
      }
      try {
        setWorkflowLoading(true);
        setWorkflowError(null);
        const data = await workflowsApi.get(workflowId);
        setWorkflow(data);
      } catch (error) {
        console.error('Failed to load workflow:', error);
        setWorkflow(null);
        setWorkflowError('加载工作流失败');
      } finally {
        setWorkflowLoading(false);
      }
    };
    loadWorkflow();
  }, [workflowId]);

  const { nodes, edges } = useMemo(() => {
    const graph = workflow?.graph;
    if (!graph?.nodes?.length) {
      return { nodes: undefined, edges: undefined };
    }
    const nodeTypeMap = new Map(nodeTypes.map((t) => [t.type, t]));

    const getPosition = (node: WorkflowGraphNode, index: number) => {
      const position = node.ui_properties?.position;
      if (position && typeof position.x === 'number' && typeof position.y === 'number') {
        return position;
      }
      const columnCount = 3;
      const column = index % columnCount;
      const row = Math.floor(index / columnCount);
      return { x: 80 + column * 280, y: 80 + row * 220 };
    };

    const graphNodes: Node<WorkflowNodeData>[] = graph.nodes.map((node, index) => {
      const title =
        (node.data?.name as string) ||
        (node.data?.title as string) ||
        (node.data?.label as string) ||
        node.id;

      const ui = node.ui_properties;
      const baseNode = {
        id: node.id,
        type: 'agent',
        position: getPosition(node, index),
        ...(ui?.width != null && { style: { width: ui.width } }),
        ...(ui?.selectable !== undefined && { selectable: ui.selectable }),
        ...(ui?.zIndex != null && { zIndex: ui.zIndex }),
      } as Node<WorkflowNodeData>;

      const modelLabel =
        (node.data?.model_name as string) ||
        (node.data?.model as string) ||
        (node.data?.model_service_provider as string) ||
        undefined;

      const prompt =
        (node.data?.prompt_template as string) ||
        (node.data?.prompt as string) ||
        (node.data?.system_prompt_template as string) ||
        (node.data?.query_prompt_template as string) ||
        undefined;

      const tools =
        (node.data?.tools as string[]) ||
        (node.data?.tool_names as string[]) ||
        undefined;

      const connectedInputs = Array.from(
        new Set(
          graph.edges
            .filter((e) => e.target === node.id && e.targetHandle)
            .map((e) => e.targetHandle as string),
        ),
      );

      const meta = nodeTypeMap.get(node.type);
      const schemaInputs = getSchemaKeys(meta?.input_schema as Record<string, unknown>);
      const schemaOutputs = getSchemaKeys(meta?.output_schema as Record<string, unknown>);
      const finalInputs = schemaInputs.length > 0 ? schemaInputs : ['—'];
      const finalOutputs = schemaOutputs.length > 0 ? schemaOutputs : ['—'];

      const ignoredKeys = new Set([
        'name',
        'title',
        'label',
        'model',
        'model_name',
        'model_service_provider',
        'custom_llm_provider',
        'prompt_template',
        'prompt',
        'system_prompt_template',
        'query_prompt_template',
        'tools',
        'tool_names',
      ]);

      const formatValue = (value: unknown) => {
        let display = '';
        if (Array.isArray(value)) {
          display = value.length > 3 ? `${value.slice(0, 3).join(', ')}…` : value.join(', ');
        } else if (typeof value === 'object') {
          display = JSON.stringify(value);
        } else {
          display = String(value);
        }
        return display.length > 48 ? `${display.slice(0, 48)}…` : display;
      };

      const detailsList = Object.entries(node.data ?? {})
        .filter(([key, value]) => !ignoredKeys.has(key) && value !== undefined && value !== null)
        .map(([key, value]) => {
          return { label: key, value: formatValue(value) };
        });

      let details = detailsList.slice(0, 3);
      let moreDetails = detailsList.slice(3, 8);
      let finalPrompt = prompt;
      const isLlm = node.type === 'llm';

      // 与节点拖入时的渲染保持一致：无数据时补全占位，保证展开布局
      if (details.length === 0) {
        details = isLlm
          ? [
              { label: 'type', value: node.type },
              { label: 'temperature', value: '0.7' },
            ]
          : [{ label: 'type', value: node.type }];
      }
      if (moreDetails.length === 0 && isLlm) {
        moreDetails = [
          { label: 'model', value: '—' },
          { label: 'max_tokens', value: '—' },
        ];
      }
      if (finalPrompt === undefined && isLlm) finalPrompt = ' ';

      return {
        ...baseNode,
        data: {
          name: title,
          subtitle: node.type,
          nodeType: node.type,
          modelLabel,
          prompt: finalPrompt,
          tools,
          inputs: finalInputs,
          outputs: finalOutputs,
          details,
          moreDetails,
          fieldValues: node.data ?? {},
          connectedInputs,
        },
      };
    });

    const graphEdges: Edge[] = graph.edges.map((edge: WorkflowGraphEdge, index: number) => ({
      id: edge.id || `edge-${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle ?? undefined,
      targetHandle: edge.targetHandle ?? undefined,
      animated: true,
    }));

    return { nodes: graphNodes, edges: graphEdges };
  }, [workflow, nodeTypes]);

  const handleRunFlow = async () => {
    if (!workflowId) return;
    const query = window.prompt('请输入调试 Query', 'hello');
    if (!query) return;
    try {
      const result = await workflowsApi.run(workflowId, { input: { query } });
      console.log('Debug flow result:', result);
    } catch (error) {
      console.error('Debug flow failed:', error);
      alert('运行失败，请稍后重试。');
    }
  };

  /** 将画布当前 nodes/edges 转为 WorkflowGraph，与已有 workflow.graph 合并后调用 PUT /workflows/{id} 保存 */
  const handleSave = async (canvasNodes: Node<WorkflowNodeData>[], canvasEdges: Edge[]) => {
    if (!workflowId || !workflow) return;
    setSaveError(null);
    setSaveLoading(true);
    try {
      const existingById = new Map(
        (workflow.graph?.nodes ?? []).map((n) => [n.id, n])
      );
      const graphNodes: WorkflowGraphNode[] = canvasNodes.map((node) => {
        const existing = existingById.get(node.id);
        const d = node.data as Record<string, unknown> | undefined;
        const fieldValues = (d?.fieldValues as Record<string, unknown>) ?? {};
        const data: Record<string, unknown> = {
          ...(existing?.data ?? {}),
          ...fieldValues,
          name: d?.name ?? node.id,
        };
        if (d?.subtitle != null) data.type = d.subtitle;
        if (d?.modelLabel != null) data.model_name = d.modelLabel;
        if (d?.prompt != null) data.prompt_template = d.prompt;
        if (d?.tools != null) data.tools = d.tools;
        const width = node.style?.width;
        const ui_properties: WorkflowGraphNode['ui_properties'] = {
          ...(existing?.ui_properties ?? {}),
          position: node.position,
          ...(width != null && typeof width === 'number' && { width }),
        };
        const savedType =
          (d?.nodeType as string) ??
          (typeof existing?.type === 'string' && existing.type ? existing.type : null) ??
          (node.type as string) ??
          'agent';
        return {
          id: node.id,
          type: savedType,
          data,
          ui_properties,
        };
      });
      const graphEdges: WorkflowGraphEdge[] = canvasEdges.map((e, i) => ({
        id: e.id ?? `edge-${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? undefined,
        targetHandle: e.targetHandle ?? undefined,
      }));
      const graph: WorkflowGraph = { nodes: graphNodes, edges: graphEdges };
      const updated = await workflowsApi.update(workflowId, { graph });
      setWorkflow(updated);
    } catch (error) {
      console.error('Save workflow failed:', error);
      setSaveError('保存失败，请稍后重试。');
    } finally {
      setSaveLoading(false);
    }
  };

  return (
    <div className="workflow-editor-page">
      {showPanel && <WorkflowsPanel />}
      {workflowId && (workflowLoading || workflowError || workflow?.title || saveError) && (
        <div className="workflow-editor-status">
          <span className="workflow-editor-status-title">
            {workflowLoading
              ? '加载中...'
              : saveLoading
              ? '保存中...'
              : saveError
              ? saveError
              : workflowError
              ? workflowError
              : workflow?.title || workflowId}
          </span>
        </div>
      )}
      <section className="workflow-canvas-wrapper">
        <div className="workflow-canvas-inner">
          <ErrorBoundary>
            <EditorUiProvider>
              <NodeflowCanvas
              onSelectionChange={(node) => {
                setSelection(node);
                setEditingLabel(node?.label ?? '');
              }}
              selectedNodeId={selection?.id ?? null}
              selectedLabel={editingLabel}
              nodes={nodes}
              edges={edges}
              onRunFlow={handleRunFlow}
              onSave={handleSave}
              nodeTypeMetadata={nodeTypes}
            />
            </EditorUiProvider>
          </ErrorBoundary>
        </div>
      </section>
    </div>
  );
}

