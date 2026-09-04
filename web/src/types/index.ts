export interface Collection {
  id?: string;
  title?: string;
  type?: string;
  description?: string;
  status?: 'ACTIVE' | 'INACTIVE' | 'DELETED';
  created?: string;
  updated?: string;
  is_published?: boolean;
  published_at?: string;
  config?: object;
}

export interface CollectionView {
  id?: string;
  title?: string;
  description?: string;
  type?: string;
  status?: 'ACTIVE' | 'INACTIVE' | 'DELETED';
  created?: string;
  updated?: string;
  owner_user_id?: string;
  owner_username?: string;
  is_published?: boolean;
  published_at?: string;
}

export interface CollectionViewList {
  items?: CollectionView[];
  pageResult?: {
    page_number?: number;
    page_size?: number;
    count?: number;
  };
}

export interface CollectionCreate {
  title?: string;
  description?: string;
  type?: string;
  config?: any;
  source?: any;
}

export interface CollectionUpdate {
  title?: string;
  description?: string;
  config?: any;
  source?: any;
}

export interface SharingStatusResponse {
  is_published: boolean;
  published_at?: string | null;
}

// Marketplace shared collection types
export interface SharedCollectionConfig {
  enable_vector_and_fulltext: boolean;
  enable_knowledge_graph: boolean;
  enable_summary: boolean;
  enable_vision: boolean;
}

export interface SharedCollection {
  id: string;
  title: string;
  description?: string;
  owner_user_id: string;
  owner_username?: string;
  subscription_id?: string | null;
  gmt_subscribed?: string | null;
  config: SharedCollectionConfig;
}

export interface SharedCollectionList {
  items: SharedCollection[];
  total: number;
  page: number;
  page_size: number;
}

export interface Document {
  id?: string;
  collection_id?: string;
  // 前端使用的字段名（映射后）
  file_name?: string;
  file_size?: number;
  file_type?: string;
  status?: string;
  vector_status?: string;
  fulltext_status?: string;
  graph_status?: string;
  summary_status?: string;
  vision_status?: string;
  created?: string;
  updated?: string;
  // 后端实际返回的字段名（原始数据）
  name?: string;
  size?: number;
  vector_index_status?: string;
  fulltext_index_status?: string;
  graph_index_status?: string;
  summary_index_status?: string;
  vision_index_status?: string;
  vector_index_updated?: string | null;
  fulltext_index_updated?: string | null;
  graph_index_updated?: string | null;
  summary_index_updated?: string | null;
  vision_index_updated?: string | null;
  summary?: string | null;
}

export interface DocumentList {
  items?: Document[];
  // 后端实际返回的分页信息
  total?: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
  has_next?: boolean;
  has_prev?: boolean;
  // 前端期望的分页信息（兼容性）
  pageResult?: {
    page_number?: number;
    page_size?: number;
    count?: number;
  };
}

// 可用模型相关类型
export interface ModelConfig {
  model: string;
  model_service_provider?: string | null;
  custom_llm_provider?: string;
  temperature?: number;
  max_tokens?: number | null;
  max_completion_tokens?: number | null;
  timeout?: number | null;
  top_n?: number | null;
  tags?: string[];
}

export interface AvailableModelItem {
  name: string;
  completion_dialect: string;
  embedding_dialect: string;
  rerank_dialect: string;
  label: string;
  allow_custom_base_url: boolean;
  base_url: string;
  embedding: ModelConfig[];
  completion: ModelConfig[];
  rerank: ModelConfig[];
}

export interface AvailableModelsResponse {
  items: AvailableModelItem[];
  pageResult?: any;
}

/** 节点画布展示属性，与后端 / nodetool 格式对齐 */
export interface NodeUIProperties {
  position?: { x: number; y: number };
  zIndex?: number;
  width?: number;
  height?: number;
  selectable?: boolean;
  bypassed?: boolean;
  [key: string]: any;
}

export interface Bot {
  id?: string;
  title?: string;
  description?: string;
  status?: 'ACTIVE' | 'INACTIVE' | 'DELETED';
  created?: string;
  updated?: string;
  owner_user_id?: string;
  is_published?: boolean;
  published_at?: string;
  config?: any;
}

export interface BotView {
  id?: string;
  title?: string;
  description?: string;
  status?: 'ACTIVE' | 'INACTIVE' | 'DELETED';
  created?: string;
  updated?: string;
  owner_user_id?: string;
  is_published?: boolean;
  published_at?: string;
  config?: any;
}

export interface BotViewList {
  items?: BotView[];
  pageResult?: {
    page_number?: number;
    page_size?: number;
    count?: number;
  };
}

// 聊天历史消息类型
export interface ChatHistoryMessage {
  id?: string;
  part_id?: string;
  type?: string;
  timestamp?: number;
  role?: 'human' | 'assistant' | 'system';
  data?: string;
  references?: any;
  urls?: any;
  feedback?: any;
  files?: any;
   // 结构化元数据（例如 AG-UI 工具调用信息）
  metadata?: any;
}

// 聊天历史类型（二维数组，每个内部数组代表一个对话轮次）
export type ChatHistory = ChatHistoryMessage[][];

// 聊天详情类型（用于获取单个聊天）
export interface ChatView {
  id?: string;
  title?: string;
  bot_id?: string;
  peer_id?: string | null;
  peer_type?: string;
  history?: ChatHistory;
  status?: string | null;
  created?: string;
  updated?: string;
}

// 聊天列表项类型（简化版，用于列表）
export interface Chat {
  id?: string;
  title?: string;
  bot_id?: string;
  created?: string;
  updated?: string;
}

export interface ChatCreate {
  title?: string;
}

export interface ChatList {
  items?: Chat[];
  pageResult?: {
    page_number?: number;
    page_size?: number;
    count?: number;
  };
}

// 聊天完成相关类型
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatCompletionRequest {
  message: string;
  // 以下参数作为查询参数传递
  bot_id?: string;
  chat_id?: string;
  stream?: boolean; // 默认为 true，使用流式返回
  model_name?: string;
  model_service_provider?: string;
  custom_llm_provider?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
   web_search_enabled?: boolean;
}

export interface ChatCompletionResponse {
  type?: string;
  id?: string;
  data?: string;
  timestamp?: number;
  // 兼容旧格式
  object?: string;
  created?: number;
  model?: string;
  choices?: Array<{
    index?: number;
    message?: ChatMessage;
    finish_reason?: string;
  }>;
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
}

/** AG-UI Run 请求体：POST /api/v1/agents/{agent_id}/chats/{chat_id}/ag-ui */
export interface AGUIRunRequestBody {
  thread_id: string;
  run_id: string;
  parent_run_id?: string;
  messages: Array<{ role: string; content: string }>;
  forwarded_props?: {
    query?: string;
    collections?: Array<{ id?: string; title?: string }>;
    completion?: Record<string, unknown>;
    language?: string;
    files?: Array<{ id?: string; name?: string }>;
    web_search_enabled?: boolean;
  };
}

/** AG-UI 协议 SSE 事件（部分常用类型） */
export interface AGUIStreamEvent {
  type?: string;
  messageId?: string;
  delta?: string;
  message?: string;
  content?: string;
  threadId?: string;
  runId?: string;
}

/** WebSocket connect 消息体：/api/v1/agents/{agent_id}/chats/{chat_id}/connect */
export interface AgentConnectPayload {
  query: string;
  collections?: Array<{ id?: string; title?: string }>;
  language?: string;
  completion?: {
    model?: string | null;
    model_service_provider?: string | null;
    custom_llm_provider?: string | null;
    temperature?: number | null;
    max_tokens?: number | null;
    max_completion_tokens?: number | null;
    timeout?: number | null;
    top_n?: number | null;
    tags?: string[];
  };
  files?: Array<{ id?: string; name?: string }>;
  web_search_enabled?: boolean;
}

// 模型供应商相关类型
export interface ModelProvider {
  name: string;
  user_id?: string;
  label?: string;
  completion_dialect?: string;
  embedding_dialect?: string;
  rerank_dialect?: string;
  allow_custom_base_url?: boolean;
  base_url?: string;
  extra?: any;
  created?: string;
  updated?: string;
  api_key?: string;
  enabled?: boolean;
  status?: 'enable' | 'disable';
}

export interface ModelProviderList {
  providers?: ModelProvider[];
  models?: ModelProviderModel[];
}

export interface ModelProviderModel {
  provider_name: string;
  api: 'embedding' | 'rerank' | 'completion' | string;
  model: string;
  custom_llm_provider?: string;
  context_window?: number | null;
  max_input_tokens?: number | null;
  max_output_tokens?: number | null;
  tags?: string[];
  created?: string;
  updated?: string;
}

export interface ModelProviderModelsResponse {
  items?: ModelProviderModel[];
  models?: ModelProviderModel[];
}

export interface ModelProviderModelCreate {
  model: string;
  api: 'embedding' | 'rerank' | 'completion' | string;
  custom_llm_provider?: string;
  context_window?: number | null;
  max_input_tokens?: number | null;
  max_output_tokens?: number | null;
  tags?: string[];
}

export interface ModelProviderCreate {
  name: string;
  label?: string;
  base_url?: string;
  completion_dialect?: string;
  embedding_dialect?: string;
  rerank_dialect?: string;
}

export interface ModelProviderUpdate {
  name?: string;
  base_url?: string;
  label?: string;
  completion_dialect?: string;
  embedding_dialect?: string;
  rerank_dialect?: string;
  enabled?: boolean;
  api_key?: string;
  status?: 'enable' | 'disable';
}

// Knowledge Graph 相关类型
export interface GraphNodeProperties {
  entity_id?: string;
  entity_type?: string;
  name?: string;
  description?: string;
  summary?: string;
  source_id?: string;
  file_path?: string;
  created_at?: number;
  [key: string]: any;
}

export interface GraphEdgeProperties {
  weight?: number;
  description?: string;
  fact?: string;
  name?: string;
  keywords?: string;
  episodes?: string;
  valid_from?: number;
  source_id?: string;
  file_path?: string;
  created_at?: number;
  [key: string]: any;
}

export interface GraphNode {
  id: string;
  labels: string[];
  properties: GraphNodeProperties;
}

export interface GraphEdge {
  id: string;
  type?: string;
  source: string;
  target: string;
  properties: GraphEdgeProperties;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  is_truncated: boolean;
}

export interface GraphLabelsResponse {
  labels: string[];
}

// 认证相关类型
export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  token?: string;
}

export interface RegisterResponse {
  message?: string;
  user_id?: string;
  email?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  message?: string;
  id?: string;
  user_id?: string;
  username?: string;
  email?: string;
  token?: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export interface ChangePasswordResponse {
  message?: string;
}
