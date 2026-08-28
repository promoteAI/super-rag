import axios, { AxiosError } from 'axios';
import type { Collection, CollectionViewList, CollectionCreate, CollectionUpdate, DocumentList, AvailableModelsResponse, BotViewList, BotView, ChatList, Chat, ChatView, ChatCreate, ChatCompletionRequest, ChatCompletionResponse, AgentConnectPayload, AGUIRunRequestBody, AGUIStreamEvent, ModelProviderList, ModelProvider, ModelProviderCreate, ModelProviderUpdate, ModelProviderModelsResponse, ModelProviderModel, ModelProviderModelCreate, RegisterRequest, RegisterResponse, LoginRequest, LoginResponse, ChangePasswordRequest, ChangePasswordResponse, KnowledgeGraph, GraphLabelsResponse, SharingStatusResponse, SharedCollectionList, SharedCollection } from '../types';

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
  withCredentials: true, // 支持 Cookie 认证
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      // 服务器返回了错误状态码
      const status = error.response.status;
      const responseData = error.response.data as any;
      // 优先使用 detail 字段，如果没有则使用 message 字段
      const errorMessage = responseData?.detail || responseData?.message || error.message;
      
      if (status === 401) {
        console.error('Unauthorized - Please login');
      } else if (status === 403) {
        console.error('Forbidden - Access denied');
      } else if (status === 404) {
        console.error('Not found');
      } else if (status >= 500) {
        console.error('Server error');
      }
      
      return Promise.reject(new Error(errorMessage || `Request failed with status ${status}`));
    } else if (error.request) {
      // 请求已发出但没有收到响应
      return Promise.reject(new Error('Network error - Please check your connection'));
    } else {
      // 其他错误
      return Promise.reject(error);
    }
  }
);

// Auth API
export const authApi = {
  // 登录
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/login', data);
    const loginData = response.data;
    
    // 如果响应中包含 token，保存到 localStorage（如果使用 Cookie 认证，token 会自动通过 Cookie 处理）
    if (loginData.token) {
      localStorage.setItem('auth_token', loginData.token);
    }
    
    // 保存用户信息（后端返回 id，兼容 user_id）
    const userId = loginData.user_id ?? loginData.id;
    if (userId) {
      localStorage.setItem('user_id', String(userId));
    }
    // 保存用户名（优先使用响应中的，否则使用登录时输入的用户名）
    const username = loginData.username || data.username;
    if (username) {
      localStorage.setItem('user_username', username);
    }
    if (loginData.email) {
      localStorage.setItem('user_email', loginData.email);
    }
    
    return loginData;
  },
  // 注册
  register: async (data: RegisterRequest): Promise<RegisterResponse> => {
    const response = await apiClient.post<RegisterResponse>('/register', data);
    return response.data;
  },
  // 登出
  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/logout');
    } catch (error) {
      // 即使登出接口失败，也清除本地存储
      console.error('Logout API error:', error);
    } finally {
      // 清除本地存储的认证信息
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_id');
      localStorage.removeItem('user_username');
      localStorage.removeItem('user_email');
    }
  },
  // 修改密码
  changePassword: async (data: ChangePasswordRequest): Promise<ChangePasswordResponse> => {
    const response = await apiClient.post<ChangePasswordResponse>('/change-password', data);
    return response.data;
  },
};

// Collections API
export const collectionsApi = {
  // 获取集合列表
  list: async (page: number = 1, pageSize: number = 50): Promise<CollectionViewList> => {
    const response = await apiClient.get<CollectionViewList>('/collections', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  // 获取单个集合
  get: async (collectionId: string): Promise<Collection> => {
    const response = await apiClient.get<Collection>(`/collections/${collectionId}`);
    return response.data;
  },

  // 创建集合
  create: async (data: CollectionCreate): Promise<Collection> => {
    const response = await apiClient.post<Collection>('/collections', data);
    return response.data;
  },

  // 更新集合
  update: async (collectionId: string, data: CollectionUpdate): Promise<Collection> => {
    const response = await apiClient.put<Collection>(`/collections/${collectionId}`, data);
    return response.data;
  },

  // 删除集合
  delete: async (collectionId: string): Promise<Collection> => {
    const response = await apiClient.delete<Collection>(`/collections/${collectionId}`);
    return response.data;
  },

  // 获取集合文档列表
  getDocuments: async (
    collectionId: string,
    page: number = 1,
    pageSize: number = 20,
    search?: string
  ): Promise<DocumentList> => {
    const response = await apiClient.get<DocumentList>(`/collections/${collectionId}/documents`, {
      params: { page, page_size: pageSize, search },
    });
    return response.data;
  },

  // 上传文档到集合
  uploadDocuments: async (collectionId: string, files: File[]): Promise<DocumentList> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });
    
    const response = await apiClient.post<DocumentList>(
      `/collections/${collectionId}/documents`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5分钟超时，用于大文件上传
      }
    );
    return response.data;
  },

  // 删除集合中的文档
  deleteDocument: async (collectionId: string, documentId: string): Promise<void> => {
    await apiClient.delete(`/collections/${collectionId}/documents/${documentId}`);
  },

  // 重建文档索引
  rebuildDocumentIndex: async (
    collectionId: string, 
    documentId: string,
    indexTypes?: string[]
  ): Promise<void> => {
    // 如果没有指定索引类型，默认重建所有类型
    const types = indexTypes || ['VECTOR_AND_FULLTEXT', 'GRAPH', 'SUMMARY', 'VISION'];
    await apiClient.post(`/collections/${collectionId}/documents/${documentId}/rebuild_indexes`, {
      index_types: types
    });
  },

  // 重建集合中所有失败的索引
  rebuildFailedIndexes: async (collectionId: string): Promise<void> => {
    await apiClient.post(`/collections/${collectionId}/rebuild_failed_indexes`, {});
  },

  // 获取知识图谱节点标签
  getGraphLabels: async (collectionId: string): Promise<GraphLabelsResponse> => {
    const response = await apiClient.get<GraphLabelsResponse>(
      `/collections/${collectionId}/graphs/labels`
    );
    return response.data;
  },

  // 获取知识图谱数据
  getKnowledgeGraph: async (
    collectionId: string,
    label: string = '*',
    maxNodes: number = 1000,
    maxDepth: number = 3
  ): Promise<KnowledgeGraph> => {
    const response = await apiClient.get<KnowledgeGraph>(
      `/collections/${collectionId}/graphs`,
      { params: { label, max_nodes: maxNodes, max_depth: maxDepth } }
    );
    return response.data;
  },

  // 获取集合分享状态
  getSharingStatus: async (collectionId: string): Promise<SharingStatusResponse> => {
    const response = await apiClient.get<SharingStatusResponse>(
      `/collections/${collectionId}/sharing`
    );
    return response.data;
  },

  // 发布集合到市场
  publish: async (collectionId: string): Promise<SharingStatusResponse> => {
    const response = await apiClient.post<SharingStatusResponse>(
      `/collections/${collectionId}/sharing`
    );
    return response.data;
  },

  // 从市场下架集合
  unpublish: async (collectionId: string): Promise<SharingStatusResponse> => {
    const response = await apiClient.delete<SharingStatusResponse>(
      `/collections/${collectionId}/sharing`
    );
    return response.data;
  },
};

// Marketplace API
export const marketplaceApi = {
  // 列出已发布到市场的集合
  listCollections: async (page: number = 1, pageSize: number = 30): Promise<SharedCollectionList> => {
    const response = await apiClient.get<SharedCollectionList>('/marketplace/collections', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  // 列出用户订阅的集合
  listSubscribedCollections: async (page: number = 1, pageSize: number = 30): Promise<SharedCollectionList> => {
    const response = await apiClient.get<SharedCollectionList>('/marketplace/collections/subscriptions', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  // 获取市场集合详情
  getCollection: async (collectionId: string): Promise<SharedCollection> => {
    const response = await apiClient.get<SharedCollection>(`/marketplace/collections/${collectionId}`);
    return response.data;
  },

  // 获取市场集合文档列表
  getDocuments: async (
    collectionId: string,
    page: number = 1,
    pageSize: number = 20,
    search?: string
  ): Promise<DocumentList> => {
    const response = await apiClient.get<DocumentList>(`/marketplace/collections/${collectionId}/documents`, {
      params: { page, page_size: pageSize, search },
    });
    return response.data;
  },

  // 订阅市场集合
  subscribe: async (collectionId: string): Promise<SharedCollection> => {
    const response = await apiClient.post<SharedCollection>(`/marketplace/collections/${collectionId}/subscribe`);
    return response.data;
  },

  // 取消订阅市场集合
  unsubscribe: async (collectionId: string): Promise<void> => {
    await apiClient.delete(`/marketplace/collections/${collectionId}/subscribe`);
  },
};

// Available Models API
export const availableModelsApi = {
  // 获取可用模型列表
  getAvailableModels: async (): Promise<AvailableModelsResponse> => {
    const response = await apiClient.post<AvailableModelsResponse>('/available_models');
    return response.data;
  },
};

// Default Models API
export const defaultModelsApi = {
  // 获取所有场景的默认模型配置
  get: async (): Promise<{ items: Array<{
    scenario: string;
    provider_name?: string | null;
    model?: string | null;
    custom_llm_provider?: string | null;
  }> }> => {
    const response = await apiClient.get('/default_models');
    return response.data;
  },

  // 更新所有场景的默认模型配置
  update: async (data: {
    defaults: Array<{
      scenario: string;
      provider_name?: string | null;
      model?: string | null;
      custom_llm_provider?: string | null;
    }>;
  }): Promise<void> => {
    await apiClient.put('/default_models', data);
  },
};

// Agents API（原 Bots API，路径已统一为 /api/v1/agents）
export const botsApi = {
  // 获取 Agent 列表
  list: async (page: number = 1, pageSize: number = 50): Promise<BotViewList> => {
    const response = await apiClient.get<BotViewList>('/agents', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
  // 获取 Agent 详情
  get: async (agentId: string): Promise<BotView> => {
    const response = await apiClient.get<BotView>(`/agents/${agentId}`);
    return response.data;
  },
};

// Chats API（使用 /api/v1/agents/{agent_id}/chats）
export const chatsApi = {
  // 获取聊天列表
  list: async (agentId: string): Promise<ChatList> => {
    const response = await apiClient.get<ChatList>(`/agents/${agentId}/chats`);
    return response.data;
  },

  // 获取单个聊天详情
  get: async (agentId: string, chatId: string): Promise<ChatView> => {
    const response = await apiClient.get<ChatView>(`/agents/${agentId}/chats/${chatId}`);
    return response.data;
  },

  // 创建新聊天
  create: async (agentId: string, data?: ChatCreate): Promise<Chat> => {
    const response = await apiClient.post<Chat>(`/agents/${agentId}/chats`, data || {});
    return response.data;
  },

  // 生成聊天标题
  generateTitle: async (agentId: string, chatId: string): Promise<{ title: string }> => {
    const response = await apiClient.post<{ title: string }>(`/agents/${agentId}/chats/${chatId}/title`);
    return response.data;
  },

  // 更新聊天
  update: async (agentId: string, chatId: string, data: { title?: string }): Promise<ChatView> => {
    const response = await apiClient.put<ChatView>(`/agents/${agentId}/chats/${chatId}`, data);
    return response.data;
  },

  // 删除聊天
  delete: async (agentId: string, chatId: string): Promise<void> => {
    await apiClient.delete(`/agents/${agentId}/chats/${chatId}`);
  },
};

// Model Providers API (LLM Configuration)
export const modelProvidersApi = {
  // 获取 LLM 配置（模型供应商列表）
  list: async (): Promise<ModelProviderList> => {
    const response = await apiClient.get<ModelProviderList>('/llm_configuration');
    return response.data;
  },

  // 获取单个模型供应商
  get: async (providerId: string): Promise<ModelProvider> => {
    const response = await apiClient.get<ModelProvider>(`/llm_configuration/${providerId}`);
    return response.data;
  },

  // 创建模型供应商
  create: async (data: ModelProviderCreate): Promise<ModelProvider> => {
    const response = await apiClient.post<ModelProvider>('/llm_providers', data);
    return response.data;
  },

  // 更新模型供应商
  update: async (providerId: string, data: ModelProviderUpdate): Promise<ModelProvider> => {
    const response = await apiClient.put<ModelProvider>(`/llm_providers/${providerId}`, data);
    return response.data;
  },

  // 删除模型供应商
  delete: async (providerId: string): Promise<void> => {
    await apiClient.delete(`/llm_providers/${providerId}`);
  },

  // 切换模型供应商启用状态
  toggleEnabled: async (providerId: string, enabled: boolean): Promise<ModelProvider> => {
    const response = await apiClient.put<ModelProvider>(`/llm_configuration/${providerId}`, { enabled });
    return response.data;
  },

  // 获取模型供应商的模型列表
  listModels: async (
    params?: { provider_name?: string; api?: string; search?: string }
  ): Promise<ModelProviderModelsResponse | ModelProviderModel[]> => {
    const response = await apiClient.get<ModelProviderModelsResponse | ModelProviderModel[]>(
      '/llm_provider_models',
      { params }
    );
    return response.data;
  },

  // 创建模型供应商的模型
  createModel: async (
    providerName: string,
    data: ModelProviderModelCreate
  ): Promise<ModelProviderModel> => {
    const response = await apiClient.post<ModelProviderModel>(
      `/llm_providers/${providerName}/models`,
      data
    );
    return response.data;
  },

  // 更新模型供应商的模型
  updateModel: async (
    providerName: string,
    api: string,
    model: string,
    data: ModelProviderModelCreate
  ): Promise<ModelProviderModel> => {
    const encodedProvider = encodeURIComponent(providerName);
    const encodedApi = encodeURIComponent(api);
    const encodedModel = encodeURIComponent(model);
    const response = await apiClient.put<ModelProviderModel>(
      `/llm_providers/${encodedProvider}/models/${encodedApi}/${encodedModel}`,
      data
    );
    return response.data;
  },

  // 删除模型供应商的模型
  deleteModel: async (providerName: string, api: string, model: string): Promise<void> => {
    const encodedProvider = encodeURIComponent(providerName);
    const encodedApi = encodeURIComponent(api);
    const encodedModel = encodeURIComponent(model);
    await apiClient.delete(
      `/llm_providers/${encodedProvider}/models/${encodedApi}/${encodedModel}`
    );
  },

  // 更新默认模型配置
  updateDefaultModels: async (data: {
    defaults: Array<{
      scenario: string;
      custom_llm_provider: string;
      provider_name: string;
      model: string;
    }>;
  }): Promise<void> => {
    await apiClient.put('/default_models', data);
  },
};

// WebSocket 连接状态枚举
export enum WebSocketStatus {
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  RECONNECTING = 'RECONNECTING',
  ERROR = 'ERROR',
}

// WebSocket 客户端类（优化版）
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string = '';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000; // 最大重连延迟 30 秒
  private messageQueue: string[] = [];
  private isConnecting = false;
  private shouldReconnect = true; // 是否应该自动重连
  private connectionEstablished = false; // 连接是否已成功建立
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatInterval = 30000; // 心跳间隔 30 秒
  private lastHeartbeatTime = 0;
  private status: WebSocketStatus = WebSocketStatus.DISCONNECTED;
  
  // 回调函数
  private onMessageCallback?: (data: ChatCompletionResponse) => void;
  private onErrorCallback?: (error: Error) => void;
  private onCloseCallback?: () => void;
  private onStatusChangeCallback?: (status: WebSocketStatus) => void;

  constructor() {
    // 页面卸载时清理资源
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        this.cleanup();
      });
    }
  }

  // 设置状态并触发回调
  private setStatus(status: WebSocketStatus): void {
    if (this.status !== status) {
      this.status = status;
      if (this.onStatusChangeCallback) {
        this.onStatusChangeCallback(status);
      }
    }
  }

  // 获取当前状态
  getStatus(): WebSocketStatus {
    return this.status;
  }

  // 设置状态变化回调
  onStatusChange(callback: (status: WebSocketStatus) => void): void {
    this.onStatusChangeCallback = callback;
  }

  async connect(
    url: string,
    onMessage: (data: ChatCompletionResponse) => void,
    onError?: (error: Error) => void,
    onClose?: () => void
  ): Promise<void> {
    // 如果已经连接到相同的 URL，直接返回
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.url === url) {
      console.log('WebSocket 已连接到相同 URL，跳过重复连接');
      return;
    }

    // 如果正在连接，等待连接完成或失败
    if (this.isConnecting) {
      console.log('WebSocket 正在连接中，等待完成...');
      return new Promise((resolve, reject) => {
        const checkInterval = setInterval(() => {
          if (!this.isConnecting) {
            clearInterval(checkInterval);
            // 如果连接成功，resolve；如果失败，reject
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              resolve();
            } else {
              reject(new Error('等待中的连接失败'));
            }
          }
        }, 100);
        
        // 设置超时，避免无限等待
        setTimeout(() => {
          clearInterval(checkInterval);
          reject(new Error('等待连接超时'));
        }, 10000);
      });
    }

    // 保存 URL 和回调
    this.url = url;
    this.onMessageCallback = onMessage;
    this.onErrorCallback = onError;
    this.onCloseCallback = onClose;
    this.shouldReconnect = true;

    // 关闭现有连接，确保完全关闭后再建立新连接
    if (this.ws) {
      // 如果连接正在打开或已打开，先关闭（使用正常关闭代码）
      if (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.close(1000, 'Reconnecting');
        } catch (error) {
          console.warn('关闭现有 WebSocket 连接时出错:', error);
        }
      }
      this.ws = null;
    }

    // 等待一小段时间确保连接完全关闭（避免后端收到重复的 accept）
    await new Promise(resolve => setTimeout(resolve, 100));

    this.isConnecting = true;
    this.connectionEstablished = false; // 重置连接标志
    this.setStatus(WebSocketStatus.CONNECTING);

    return new Promise((resolve, reject) => {
      try {
        // 再次检查是否正在连接（防止并发调用）
        if (this.isConnecting && this.ws) {
          console.warn('检测到并发连接尝试，取消当前连接');
          reject(new Error('并发连接尝试被取消'));
          return;
        }

        // 构建 WebSocket URL
        const wsUrl = url.startsWith('ws://') || url.startsWith('wss://') 
          ? url 
          : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${url}`;

        console.log('创建新的 WebSocket 连接:', wsUrl);
        this.ws = new WebSocket(wsUrl);

        // 设置连接超时
        const connectTimeout = setTimeout(() => {
          if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
            try {
              // 使用超时关闭代码 1008 (Policy Violation) 或 1000 (Normal Closure)
              this.ws.close(1008, 'Connection timeout');
            } catch (error) {
              console.warn('关闭超时连接时出错:', error);
            }
            this.isConnecting = false;
            this.setStatus(WebSocketStatus.ERROR);
            reject(new Error('WebSocket 连接超时'));
          }
        }, 10000); // 10 秒超时

        this.ws.onopen = () => {
          clearTimeout(connectTimeout);
          this.isConnecting = false;
          this.connectionEstablished = true; // 标记连接已成功建立
          this.reconnectAttempts = 0;
          this.setStatus(WebSocketStatus.CONNECTED);
          console.log('WebSocket 连接已建立');
          
          // 启动心跳检测
          this.startHeartbeat();
          
          // 发送队列中的消息
          this.flushMessageQueue();
          
          resolve();
        };

        this.ws.onmessage = (event) => {
          // 更新心跳时间
          this.lastHeartbeatTime = Date.now();
          
          try {
            // 添加调试日志
            if ((import.meta as any).env?.DEV) {
              console.log('WebSocket 收到原始数据:', event.data);
            }
            
            // 尝试解析 JSON
            let response: ChatCompletionResponse;
            if (typeof event.data === 'string') {
              try {
                response = JSON.parse(event.data);
              } catch (parseError) {
                // 如果不是 JSON，作为纯文本处理
                console.warn('无法解析为 JSON，作为纯文本处理:', event.data);
                response = {
                  type: 'message',
                  data: event.data,
                };
              }
            } else if (event.data instanceof Blob) {
              // 如果是 Blob，需要先转换为文本
              const reader = new FileReader();
              reader.onload = () => {
                try {
                  const text = reader.result as string;
                  const parsed = JSON.parse(text);
                  if (this.onMessageCallback) {
                    this.onMessageCallback(parsed);
                  }
                } catch (error) {
                  console.error('解析 Blob 数据失败:', error);
                  if (this.onMessageCallback) {
                    this.onMessageCallback({
                      type: 'message',
                      data: reader.result as string,
                    });
                  }
                }
              };
              reader.readAsText(event.data);
              return;
            } else {
              // 其他类型，转换为文本
              response = {
                type: 'message',
                data: String(event.data),
              };
            }
            
            // 如果响应包含 message 字段（服务器直接返回的消息），转换为标准格式
            if ((response as any).message && !response.data && response.type !== 'error') {
              response = {
                type: response.type || 'message',
                data: (response as any).message,
              };
            }
            
            // 确保错误消息的 data 字段被正确提取
            if (response.type === 'error' && !response.data && (response as any).data) {
              response.data = (response as any).data;
            }
            
            // 调用消息处理回调
            if (this.onMessageCallback) {
              this.onMessageCallback(response);
            }
          } catch (error) {
            console.error('处理 WebSocket 消息失败:', error, event.data);
            if (this.onMessageCallback) {
              this.onMessageCallback({
                type: 'message',
                data: String(event.data),
              });
            }
          }
        };

        this.ws.onerror = (error) => {
          clearTimeout(connectTimeout);
          this.isConnecting = false;
          console.error('WebSocket 错误:', error);
          
          // 只有在连接未成功建立时才触发错误回调并 reject
          // 使用 connectionEstablished 标志来判断，因为 readyState 可能在 onerror 和 onopen 之间变化
          if (!this.connectionEstablished) {
            this.setStatus(WebSocketStatus.ERROR);
            if (this.onErrorCallback) {
              this.onErrorCallback(new Error('WebSocket 连接错误'));
            }
            reject(new Error('WebSocket 连接错误'));
          } else {
            // 连接已建立，只记录错误，不触发错误回调，不影响连接状态
            console.warn('WebSocket 连接已建立，但发生了错误事件（可能是消息处理错误）');
          }
        };

        this.ws.onclose = (event) => {
          clearTimeout(connectTimeout);
          this.isConnecting = false;
          this.connectionEstablished = false; // 重置连接标志
          this.stopHeartbeat();
          
          // 记录关闭信息
          const closeCode = event.code;
          const closeReason = event.reason || '';
          console.log('WebSocket 连接已关闭', {
            code: closeCode,
            reason: closeReason,
            wasClean: event.wasClean
          });
          
          // 如果是异常关闭（1006），记录警告
          if (closeCode === 1006) {
            console.warn('WebSocket 异常关闭 (1006)，可能原因：网络中断、服务器异常或连接未完全建立');
          }
          
          if (this.onCloseCallback) {
            this.onCloseCallback();
          }
          
          // 自动重连逻辑（只在非主动关闭且允许重连时）
          // 1000 是正常关闭，不应该重连
          // 1006 是异常关闭，可以尝试重连
          if (this.shouldReconnect && 
              closeCode !== 1000 && 
              this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(
              this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
              this.maxReconnectDelay
            );
            
            this.setStatus(WebSocketStatus.RECONNECTING);
            console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})，延迟 ${delay}ms...`);
            
            this.reconnectTimer = setTimeout(() => {
              if (this.shouldReconnect && this.onMessageCallback) {
                this.connect(this.url, this.onMessageCallback, this.onErrorCallback, this.onCloseCallback)
                  .catch(() => {
                    // 重连失败，忽略错误
                  });
              }
            }, delay);
          } else {
            this.setStatus(WebSocketStatus.DISCONNECTED);
            if (closeCode === 1000) {
              console.log('WebSocket 正常关闭，不进行重连');
            } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
              console.warn(`WebSocket 重连次数已达上限 (${this.maxReconnectAttempts})，停止重连`);
            }
          }
        };
      } catch (error) {
        this.isConnecting = false;
        this.setStatus(WebSocketStatus.ERROR);
        reject(error);
      }
    });
  }

  // 启动心跳检测
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.lastHeartbeatTime = Date.now();
    
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // 检查是否超过心跳间隔的 2 倍没有收到消息
        const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatTime;
        if (timeSinceLastHeartbeat > this.heartbeatInterval * 2) {
          console.warn('心跳超时，可能连接已断开');
          // 可以发送 ping 消息（如果服务器支持）
          // this.ws.send(JSON.stringify({ type: 'ping' }));
        }
      }
    }, this.heartbeatInterval);
  }

  // 停止心跳检测
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  // 发送队列中的消息
  private flushMessageQueue(): void {
    // 连接已建立，直接发送队列中的消息
    // 注意：此时连接肯定是 OPEN 状态，所以可以直接发送
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        // 使用 send 方法发送，保持一致性
        // 由于连接已建立，不会再次入队
        this.send(message);
      }
    }
  }

  send(message: string): void {
    // 确保消息是字符串格式（JSON 序列化后的字符串）
    const messageToSend = typeof message === 'string' ? message : JSON.stringify(message);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // 连接已建立，直接发送
      this.ws.send(messageToSend);
      if ((import.meta as any).env?.DEV) {
        console.log('WebSocket 发送消息:', messageToSend);
      }
    } else {
      // 如果连接未建立，将消息加入队列
      this.messageQueue.push(messageToSend);
      console.warn('WebSocket 未连接，消息已加入队列:', messageToSend);
    }
  }

  close(shouldReconnect: boolean = false): void {
    this.shouldReconnect = shouldReconnect;
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    this.stopHeartbeat();
    
    if (this.ws) {
      // 检查连接状态，只有在连接已打开或正在连接时才关闭
      // 使用正确的关闭代码和原因，避免异常关闭
      if (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN) {
        try {
          // 使用正常关闭代码 1000 (Normal Closure)
          this.ws.close(1000, 'Normal closure');
        } catch (error) {
          console.warn('关闭 WebSocket 时出错:', error);
        }
      }
      this.ws = null;
    }
    
    this.messageQueue = [];
    this.reconnectAttempts = 0;
    this.connectionEstablished = false;
    this.setStatus(WebSocketStatus.DISCONNECTED);
  }

  // 清理所有资源
  cleanup(): void {
    this.close(false);
    this.onMessageCallback = undefined;
    this.onErrorCallback = undefined;
    this.onCloseCallback = undefined;
    this.onStatusChangeCallback = undefined;
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  // 手动重连
  async reconnect(): Promise<void> {
    if (this.url && this.onMessageCallback) {
      this.close(false);
      await new Promise(resolve => setTimeout(resolve, 1000));
      return this.connect(this.url, this.onMessageCallback, this.onErrorCallback, this.onCloseCallback);
    }
  }
}

// AG-UI Run API：POST /api/v1/agents/{agent_id}/chats/{chat_id}/ag-ui，符合 AG-UI 协议
export const agUiRunApi = {
  run: async (
    agentId: string,
    chatId: string,
    body: AGUIRunRequestBody,
    onEvent: (event: AGUIStreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const baseURL = apiClient.defaults.baseURL || '/api/v1';
    const url = `${baseURL}/agents/${agentId}/chats/${chatId}/ag-ui`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      credentials: 'include',
      signal,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `AG-UI run failed: ${response.status}`);
    }
    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          if (jsonStr === '[DONE]') continue;
          try {
            const event = JSON.parse(jsonStr) as AGUIStreamEvent;
            onEvent(event);
          } catch {
            // ignore parse errors
          }
        }
      }
    }
  },
};

// Chat Completions API
export const chatCompletionsApi = {
  // WebSocket 聊天接口：/api/v1/agents/{agent_id}/chats/{chat_id}/connect
  websocket: async (
    agentId: string,
    chatId: string,
    payload: AgentConnectPayload,
    onMessage: (chunk: ChatCompletionResponse) => void,
    onError?: (error: Error) => void,
    onClose?: () => void
  ): Promise<WebSocketClient> => {
    const wsUrl = `/api/v1/agents/${agentId}/chats/${chatId}/connect`;
    const client = new WebSocketClient();

    const messageJson = JSON.stringify(payload);

    if ((import.meta as any).env?.DEV) {
      console.log('准备发送 WebSocket 消息:', messageJson);
      console.log('WebSocket URL:', wsUrl);
    }

    await client.connect(wsUrl, onMessage, onError, onClose);
    client.send(messageJson);
    return client;
  },

  // 前端聊天完成接口（支持流式和非流式）
  frontend: async (
    data: ChatCompletionRequest,
    onStreamChunk?: (chunk: ChatCompletionResponse) => void,
    signal?: AbortSignal
  ): Promise<ChatCompletionResponse | null> => {
    // 将 bot_id, chat_id, stream, model 等作为查询参数，message 作为请求体
    const {
      message,
      bot_id,
      chat_id,
      stream = true,
      model,
      model_name,
      model_service_provider,
      custom_llm_provider,
      temperature,
      max_tokens,
    } = data;
    const params: Record<string, any> = {};
    
    if (bot_id) params.bot_id = bot_id;
    if (chat_id) params.chat_id = chat_id;
    params.stream = stream; // 默认 true
    if (model) params.model = model;
    if (model_name) params.model_name = model_name;
    if (model_service_provider) params.model_service_provider = model_service_provider;
    if (custom_llm_provider) params.custom_llm_provider = custom_llm_provider;
    if (temperature !== undefined) params.temperature = temperature;
    if (max_tokens !== undefined) params.max_tokens = max_tokens;
    
    // 请求体只包含 message
    const body = {
      message: message,
    };
    
    // 如果是流式响应
    if (stream && onStreamChunk) {
      return new Promise((resolve, reject) => {
        // 构建 URL（使用相对路径，Vite 代理会处理）
        const baseURL = apiClient.defaults.baseURL || '/api/v1';
        let url = `${baseURL}/chat/completions/frontend`;
        
        // 添加查询参数
        const queryParams = new URLSearchParams();
        Object.keys(params).forEach(key => {
          queryParams.append(key, String(params[key]));
        });
        if (queryParams.toString()) {
          url += '?' + queryParams.toString();
        }
        
        let lastResponse: ChatCompletionResponse | null = null;
        let hasReceivedData = false;
        
        // 使用 fetch 发送 POST 请求并处理流式响应
        fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
          signal,
        })
          .then(response => {
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 检查 Content-Type
            const contentType = response.headers.get('content-type') || '';
            const isStreaming = contentType.includes('text/event-stream') || 
                               contentType.includes('text/plain') ||
                               contentType.includes('application/json');
            
            if (!isStreaming) {
              console.warn('Response is not streaming, content-type:', contentType);
            }
            
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            
            if (!reader) {
              throw new Error('No response body');
            }
            
            let buffer = '';
            
            const readStream = () => {
              reader.read().then(({ done, value }) => {
                if (done) {
                  // 处理剩余的 buffer
                  if (buffer.trim()) {
                    const trimmedBuffer = buffer.trim();
                    // 尝试处理多行 JSON
                    const lines = trimmedBuffer.split('\n').filter(line => line.trim());
                    for (const line of lines) {
                      try {
                        const data = JSON.parse(line);
                        const responseChunk: ChatCompletionResponse = data;
                        lastResponse = responseChunk;
                        onStreamChunk(responseChunk);
                        hasReceivedData = true;
                      } catch (error) {
                        // 忽略单行解析错误
                      }
                    }
                  }
                  if (!hasReceivedData && lastResponse) {
                    hasReceivedData = true;
                  }
                  resolve(lastResponse);
                  return;
                }
                
                // 解码数据块
                buffer += decoder.decode(value, { stream: true });
                
                // 按行处理
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // 保留最后不完整的行
                
                for (const line of lines) {
                  const trimmedLine = line.trim();
                  if (!trimmedLine) continue;
                  
                  // SSE 格式：data: {...}
                  if (trimmedLine.startsWith('data: ')) {
                    try {
                      const jsonStr = trimmedLine.slice(6);
                      if (jsonStr === '[DONE]') {
                        continue;
                      }
                      const data = JSON.parse(jsonStr);
                      const responseChunk: ChatCompletionResponse = data;
                      lastResponse = responseChunk;
                      onStreamChunk(responseChunk);
                      hasReceivedData = true;
                    } catch (error) {
                      if ((import.meta as any).env?.DEV) {
                        console.warn('Failed to parse SSE data line:', trimmedLine, error);
                      }
                    }
                  } 
                  // 直接 JSON 格式（每行一个 JSON 对象）
                  else if (trimmedLine.startsWith('{') || trimmedLine.startsWith('[')) {
                    try {
                      const data = JSON.parse(trimmedLine);
                      const responseChunk: ChatCompletionResponse = data;
                      lastResponse = responseChunk;
                      onStreamChunk(responseChunk);
                      hasReceivedData = true;
                    } catch (error) {
                      // 忽略解析错误，可能是部分 JSON
                    }
                  }
                }
                
                readStream();
              }).catch((error) => {
                console.error('Stream read error:', error);
                if (lastResponse) {
                  resolve(lastResponse);
                } else {
                  reject(error);
                }
              });
            };
            
            readStream();
          })
          .catch((error) => {
            console.error('Fetch error:', error);
            reject(error);
          });
      });
    } else {
      // 非流式响应
      const response = await apiClient.post<ChatCompletionResponse>(
        '/chat/completions/frontend',
        body,
        {
          params: Object.keys(params).length > 0 ? params : undefined,
        }
      );
      return response.data;
    }
  },
};
