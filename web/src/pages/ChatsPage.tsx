import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  Paperclip, 
  Globe, 
  ThumbsUp, 
  ThumbsDown, 
  Copy,
  Send,
  Square,
  ChevronDown,
  ChevronRight,
  Trash2,
  Menu,
  Check,
  Loader2,
  Info,
  Brain
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { MermaidDiagram } from '../components/MermaidDiagram';
import { botsApi, chatsApi, agUiRunApi, availableModelsApi, collectionsApi } from '../api/client';
import type { ModelConfig, ChatHistoryMessage, CollectionView, Chat } from '../types';
import './ChatsPage.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface AssistantToolRun {
  tool_call_id: string;
  tool_call_name?: string;
  parent_message_id?: string;
  status: 'running' | 'completed';
  args?: string;
  content?: string;
  createdAt: number;
}

interface AssistantActivitySnapshot {
  key: string;
  activityType: string;
  content: string;
  createdAt: number;
}

interface AssistantTrace {
  reasoning: string;
  tools: Record<string, AssistantToolRun>;
  activities: Record<string, AssistantActivitySnapshot>;
}

function stringifyTraceContent(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value == null) return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function ChatsPage() {
  const { chatId } = useParams<{ chatId?: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [selectedModel, setSelectedModel] = useState<ModelConfig | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelConfig[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null); // 正在流式传输的消息ID
  const [botId, setBotId] = useState<string | null>(null);
  const [collections, setCollections] = useState<CollectionView[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [showCollectionDropdown, setShowCollectionDropdown] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [currentChatTitle, setCurrentChatTitle] = useState<string | null>(null);
  const [chatList, setChatList] = useState<Chat[]>([]);
  const [chatListLoading, setChatListLoading] = useState(false);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);
  const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);
  const mentionDropdownRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const previousChatIdRef = useRef<string | undefined>(undefined);
  const messagesRef = useRef<Message[]>([]);
  const [assistantTraces, setAssistantTraces] = useState<Record<string, AssistantTrace>>({});

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 获取第一个可用的 bot
  useEffect(() => {
    const loadBot = async () => {
      try {
        const botsData = await botsApi.list();
        const bots = botsData.items || [];
        if (bots.length > 0 && bots[0].id) {
          setBotId(bots[0].id);
        }
      } catch (error) {
        console.error('Failed to load bots:', error);
      }
    };
    loadBot();
  }, []);

  // 加载聊天列表（用于左侧历史）
  useEffect(() => {
    const loadChatList = async () => {
      if (!botId) return;
      try {
        setChatListLoading(true);
        const data = await chatsApi.list(botId);
        setChatList(data.items || []);
      } catch (error) {
        console.error('Failed to load chat list:', error);
        setChatList([]);
      } finally {
        setChatListLoading(false);
      }
    };
    loadChatList();
  }, [botId]);

  // 加载历史聊天记录
  useEffect(() => {
    const loadChatHistory = async () => {
      const previousChatId = previousChatIdRef.current;
      previousChatIdRef.current = chatId;

      if (!chatId || !botId || chatId === 'new') {
        // 如果是新聊天，清空消息和标题
        setMessages([]);
        setAssistantTraces({});
        setCurrentChatTitle(null);
        setLoadingHistory(false);
        return;
      }

      // 从新会话跳转到真实 chatId 时，保留本地消息并跳过历史拉取
      if (previousChatId === 'new' && messagesRef.current.length > 0) {
        setLoadingHistory(false);
        return;
      }

      try {
        // 开始加载前，先清空消息和设置加载状态
        setMessages([]);
        setAssistantTraces({});
        setLoadingHistory(true);
        const chatData = await chatsApi.get(botId, chatId);
        
        // 设置当前会话标题
        if (chatData.title) {
          setCurrentChatTitle(chatData.title);
        } else {
          setCurrentChatTitle(null);
        }
        
        // 将历史记录转换为消息和 AG-UI 风格的 trace 结构
        const historyMessages: Message[] = [];
        const historyTraces: Record<string, AssistantTrace> = {};

        if (chatData.history && Array.isArray(chatData.history)) {
          chatData.history.forEach((turn: ChatHistoryMessage[]) => {
            turn.forEach((msg: ChatHistoryMessage) => {
              if (!msg.role) return;

              const msgId = msg.id || msg.part_id || String(msg.timestamp ?? Date.now());
              const ts = msg.timestamp ? new Date(msg.timestamp * 1000) : new Date();

              // 用户消息：使用 part_id 作为唯一 id，避免与助手消息共享 message_id 导致 React key 重复
              if (msg.role === 'human') {
                if (msg.type === 'message' && msg.data) {
                  historyMessages.push({
                    id: msg.part_id || `user-${msgId}`,
                    role: 'user',
                    content: msg.data,
                    timestamp: ts,
                  });
                }
                return;
              }

              // 以下是助手侧的历史分段
              if (msg.type === 'tool_call_result') {
                const meta = (msg as any).metadata || {};
                const toolMeta = meta.agui_tool_call || meta.tool_call || {};
                const toolCallId = toolMeta.tool_call_id || toolMeta.id || `history-tool-${msgId}`;
                const toolName = toolMeta.tool_name || toolMeta.name || 'tool';

                if (!historyTraces[msgId]) {
                  historyTraces[msgId] = { reasoning: '', tools: {}, activities: {} };
                }

                historyTraces[msgId].tools[toolCallId] = {
                  tool_call_id: toolCallId,
                  tool_call_name: toolName,
                  parent_message_id: msgId,
                  status: 'completed',
                  args: toolMeta.args,
                  content: msg.data ?? '',
                  createdAt: ts.getTime(),
                };
              } else if (msg.type === 'thinking') {
                if (!historyTraces[msgId]) {
                  historyTraces[msgId] = { reasoning: '', tools: {}, activities: {} };
                }
                historyTraces[msgId].reasoning += msg.data ?? '';
              } else if (msg.type === 'message') {
                // 最终助手回答：构建一条助手消息，并附上同 message_id 下累积的 trace
                if (msg.data) {
                  historyMessages.push({
                    id: msgId,
                    role: 'assistant',
                    content: msg.data,
                    timestamp: ts,
                  });
                }
              }
            });
          });
        }

        // DB DateTime 精度为秒级，同秒内用户消息和助手消息的顺序可能不确定
        // 通过相邻交换修正：助手消息不应出现在紧跟其后的用户消息之前
        for (let i = 1; i < historyMessages.length; i++) {
          const prev = historyMessages[i - 1];
          const curr = historyMessages[i];
          if (
            prev.role === 'assistant' &&
            curr.role === 'user' &&
            Math.abs(prev.timestamp.getTime() - curr.timestamp.getTime()) < 2000
          ) {
            historyMessages[i - 1] = curr;
            historyMessages[i] = prev;
          }
        }

        setMessages(historyMessages);
        setAssistantTraces(historyTraces);
      } catch (error) {
        console.error('Failed to load chat history:', error);
        // 如果加载失败，保持当前状态（可能是新聊天）
        setCurrentChatTitle(null);
        setMessages([]);
        setAssistantTraces({});
      } finally {
        setLoadingHistory(false);
      }
    };

    if (botId) {
      loadChatHistory();
    }
  }, [chatId, botId]);

  const getModelKey = useCallback(
    (model: ModelConfig) =>
      `${model.model}|${model.custom_llm_provider ?? ''}|${model.model_service_provider ?? ''}`,
    []
  );

  // 获取可用模型列表
  useEffect(() => {
    const loadAvailableModels = async () => {
      try {
        setModelsLoading(true);
        const response = await availableModelsApi.getAvailableModels();
        
        // 从所有模型提供者中提取 completion 模型
        const completionModelSet = new Set<string>();
        const completionList: ModelConfig[] = [];
        
        response.items?.forEach((item) => {
          // 提取 completion 模型
          item.completion?.forEach((model: ModelConfig) => {
            if (model.model) {
              const key = getModelKey(model);
              if (!completionModelSet.has(key)) {
                completionModelSet.add(key);
                completionList.push(model);
              }
            }
          });
        });
        
        // 排序（按模型名）
        completionList.sort((a, b) => a.model.localeCompare(b.model));
        
        // 更新模型列表
        if (completionList.length > 0) {
          setAvailableModels(completionList);
          // 如果当前选择的模型不在新列表中，使用第一个模型
          setSelectedModel((prev) => {
            if (!prev) return completionList[0];
            const prevKey = getModelKey(prev);
            const exists = completionList.some((model) => getModelKey(model) === prevKey);
            return exists ? prev : completionList[0];
          });
        }
      } catch (error) {
        console.error('Failed to load available models:', error);
        // 使用默认模型列表作为后备
        const defaultModels: ModelConfig[] = [
          { model: 'google/gemini-2.5-flash' },
          { model: 'gpt-4' },
          { model: 'claude-3' },
        ];
        setAvailableModels(defaultModels);
        setSelectedModel((prev) => prev || defaultModels[0]);
      } finally {
        setModelsLoading(false);
      }
    };
    
    loadAvailableModels();
  }, [getModelKey]);

  // 监听聊天标题更新事件
  useEffect(() => {
    const handleChatTitleUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ chatId?: string; title?: string }>).detail;
      // 如果更新的标题是当前会话的，更新标题
      if (detail?.chatId === chatId && detail?.title) {
        setCurrentChatTitle(detail.title);
      }
      // 刷新聊天列表
      if (botId && detail?.chatId) {
        chatsApi.list(botId).then(data => {
          setChatList(data.items || []);
        }).catch(err => {
          console.error('Failed to refresh chat list:', err);
        });
      }
    };

    window.addEventListener('chat-title-updated', handleChatTitleUpdated as EventListener);
    return () =>
      window.removeEventListener('chat-title-updated', handleChatTitleUpdated as EventListener);
  }, [chatId, botId]);

  // 获取集合列表（用于 @ 提示）
  useEffect(() => {
    const loadCollections = async () => {
      try {
        setCollectionsLoading(true);
        const response = await collectionsApi.list(1, 50);
        setCollections(response.items || []);
      } catch (error) {
        console.error('Failed to load collections:', error);
        setCollections([]);
      } finally {
        setCollectionsLoading(false);
      }
    };

    loadCollections();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(target)) {
        setShowModelDropdown(false);
      }
      if (mentionDropdownRef.current && !mentionDropdownRef.current.contains(target)) {
        setShowCollectionDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || isLoading || !botId || !selectedModel?.model) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    // 立即添加用户消息
    setMessages(prev => [...prev, userMessage]);
    const currentInput = inputValue;
    const isFirstMessage = messages.length === 0; // 仅首次发消息时生成标题
    setInputValue('');
    setIsLoading(true);

    let assistantMessageId = '';
    try {
      // 如果是新聊天，先创建聊天
      let currentChatId = chatId && chatId !== 'new' ? chatId : null;
      if (!currentChatId && botId) {
        try {
          const newChat = await chatsApi.create(botId);
          if (newChat.id) {
            currentChatId = newChat.id;
            // 使用路由导航更新 URL，确保参数同步
            navigate(`/chats/${newChat.id}`, { replace: true });
          }
        } catch (error) {
          console.error('Failed to create new chat:', error);
          // 继续发送消息，后端可能会自动创建
        }
      }

      // 没有有效的 chatId 时不再回退到非 AG-UI 通道，直接报错
      if (!currentChatId) {
        throw new Error('无法创建聊天会话，请稍后重试。');
      }

      // 构建 WebSocket 消息体：/api/v1/agents/{agent_id}/chats/{chat_id}/connect 格式
      const connectPayload = {
        query: currentInput,
        collections: [],
        language: 'zh-CN',
        completion: {
          model: selectedModel.model ?? null,
          model_service_provider: selectedModel.model_service_provider ?? 'openai',
          custom_llm_provider: selectedModel.custom_llm_provider ?? 'openai',
          temperature: 0.1,
          max_tokens: null,
          max_completion_tokens: null,
          timeout: null,
          top_n: null,
          tags: [],
        },
        files: [],
        web_search_enabled: webSearchEnabled,
      };

      if ((import.meta as any).env?.DEV) {
        console.log('Chat connect payload:', JSON.stringify(connectPayload, null, 2));
      }

      // 创建助手消息占位符
      assistantMessageId = (Date.now() + 1).toString();
      const aiMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(), // 时间戳在消息完全返回后才会显示
      };
      
      // 立即添加空消息，用于流式更新
      setMessages(prev => [...prev, aiMessage]);
      setAssistantTraces((prev) => ({
        ...prev,
        [assistantMessageId]: {
          reasoning: '',
          tools: {},
          activities: {},
        },
      }));
      // 标记为正在流式传输
      setStreamingMessageId(assistantMessageId);

      let streamEnded = false;
      let receivedResponse = false;

      try {
        // 使用 AG-UI 接口：POST /api/v1/agents/{agent_id}/chats/{chat_id}/ag-ui，符合 AG-UI 协议
        const agUiBody = {
          thread_id: currentChatId,
          run_id: assistantMessageId,
          messages: [
            ...messages.map((m) => ({ role: m.role, content: m.content })),
            { role: 'user' as const, content: currentInput },
          ],
          forwarded_props: {
            query: currentInput,
            language: connectPayload.language || 'zh-CN',
            completion: connectPayload.completion,
            web_search_enabled: webSearchEnabled,
          },
        };
        await agUiRunApi.run(
          botId,
          currentChatId,
          agUiBody,
          (event) => {
            const t = event.type;
            const eventTime = Date.now();

            // 收到任意 AG-UI 事件都视为已有响应
            receivedResponse = true;

            if (t === 'TOOL_CALL_START') {
              const anyEvent = event as any;
              const toolCallId = anyEvent.tool_call_id || anyEvent.toolCallId;
              if (toolCallId) {
                const argsRaw = anyEvent.tool_call_args || anyEvent.toolCallArgs;
                setAssistantTraces((prev) => ({
                  ...prev,
                  [assistantMessageId]: {
                    reasoning: prev[assistantMessageId]?.reasoning ?? '',
                    activities: prev[assistantMessageId]?.activities ?? {},
                    tools: {
                      ...(prev[assistantMessageId]?.tools ?? {}),
                      [toolCallId]: {
                        tool_call_id: toolCallId,
                        tool_call_name:
                          anyEvent.tool_call_name || anyEvent.toolCallName ||
                          prev[assistantMessageId]?.tools?.[toolCallId]?.tool_call_name,
                        parent_message_id:
                          anyEvent.parent_message_id || anyEvent.parentMessageId ||
                          prev[assistantMessageId]?.tools?.[toolCallId]?.parent_message_id,
                        status: 'running',
                        args:
                          argsRaw ||
                          prev[assistantMessageId]?.tools?.[toolCallId]?.args,
                        content: prev[assistantMessageId]?.tools?.[toolCallId]?.content,
                        createdAt:
                          prev[assistantMessageId]?.tools?.[toolCallId]?.createdAt ?? eventTime,
                      },
                    },
                  },
                }));
              }
            } else if (t === 'REASONING_MESSAGE_CHUNK' && event.delta) {
              setAssistantTraces((prev) => ({
                ...prev,
                [assistantMessageId]: {
                  reasoning: (prev[assistantMessageId]?.reasoning ?? '') + event.delta,
                  tools: prev[assistantMessageId]?.tools ?? {},
                  activities: prev[assistantMessageId]?.activities ?? {},
                },
              }));
            } else if (t === 'ACTIVITY_SNAPSHOT') {
              const anyEvent = event as any;
              const activityType = anyEvent.activity_type || anyEvent.activityType || 'ACTIVITY';
              const key = String(activityType);
              const content = stringifyTraceContent(anyEvent.content);
              setAssistantTraces((prev) => ({
                ...prev,
                [assistantMessageId]: {
                  reasoning: prev[assistantMessageId]?.reasoning ?? '',
                  tools: prev[assistantMessageId]?.tools ?? {},
                  activities: {
                    ...(prev[assistantMessageId]?.activities ?? {}),
                    [key]: {
                      key,
                      activityType: key,
                      content,
                      createdAt: eventTime,
                    },
                  },
                },
              }));
            } else if (t === 'TOOL_CALL_END') {
              const anyEvent = event as any;
              const toolCallId = anyEvent.tool_call_id || anyEvent.toolCallId;
              if (toolCallId) {
                setAssistantTraces((prev) => {
                  const existing = prev[assistantMessageId]?.tools?.[toolCallId];
                  if (!existing) return prev;
                  return {
                    ...prev,
                    [assistantMessageId]: {
                      ...prev[assistantMessageId],
                      tools: {
                        ...prev[assistantMessageId].tools,
                        [toolCallId]: { ...existing, status: 'completed' },
                      },
                    },
                  };
                });
              }
            } else if (t === 'TOOL_CALL_RESULT') {
              const anyEvent = event as any;
              const toolCallId = anyEvent.tool_call_id || anyEvent.toolCallId;
              if (toolCallId) {
                const content = stringifyTraceContent(anyEvent.content ?? anyEvent.data ?? '');
                setAssistantTraces((prev) => {
                  const existing = prev[assistantMessageId]?.tools?.[toolCallId];
                  return {
                    ...prev,
                    [assistantMessageId]: {
                      reasoning: prev[assistantMessageId]?.reasoning ?? '',
                      activities: prev[assistantMessageId]?.activities ?? {},
                      tools: {
                        ...(prev[assistantMessageId]?.tools ?? {}),
                        [toolCallId]: {
                          tool_call_id: toolCallId,
                          tool_call_name:
                            anyEvent.tool_call_name || anyEvent.toolCallName ||
                            existing?.tool_call_name,
                          parent_message_id:
                            anyEvent.parent_message_id || anyEvent.parentMessageId ||
                            existing?.parent_message_id,
                          status: 'completed',
                          args: existing?.args,
                          content,
                          createdAt: existing?.createdAt ?? eventTime,
                        },
                      },
                    },
                  };
                });
              }
            }

            if (t === 'TEXT_MESSAGE_CONTENT' && event.delta) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId ? { ...msg, content: msg.content + event.delta } : msg
                )
              );
            } else if (t === 'RUN_FINISHED') {
              streamEnded = true;
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId ? { ...msg, timestamp: new Date() } : msg
                )
              );
              setStreamingMessageId(null);
              setAssistantTraces((prev) => {
                const trace = prev[assistantMessageId];
                if (!trace) return prev;
                const tools = trace.tools;
                const hasRunning = Object.values(tools).some((t) => t.status === 'running');
                if (!hasRunning) return prev;
                const updated = { ...tools };
                for (const [k, v] of Object.entries(updated)) {
                  if (v.status === 'running') updated[k] = { ...v, status: 'completed' };
                }
                return { ...prev, [assistantMessageId]: { ...trace, tools: updated } };
              });
            } else if (t === 'RUN_ERROR') {
              streamEnded = true;
              const errMsg = event.message || 'Unknown error';
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: (msg.content || '') + '\n\n❌ ' + errMsg, timestamp: new Date() }
                    : msg
                )
              );
              setStreamingMessageId(null);
            }
          },
          controller.signal
        );
      } catch (wsError) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content:
                    (msg.content || '') +
                    '\n\n❌ ' +
                    (wsError instanceof Error ? wsError.message : '请求失败'),
                  timestamp: new Date(),
                }
              : msg
          )
        );
        setStreamingMessageId(null);
      }
      
      // 仅在首次发消息时生成并更新标题（避免每次回复都调用 title API）
      if (isFirstMessage && streamEnded && botId && currentChatId) {
        try {
          const titleResponse = await chatsApi.generateTitle(botId, currentChatId);
          const generatedTitle = titleResponse.title;
          if (generatedTitle) {
            await chatsApi.update(botId, currentChatId, { title: generatedTitle });
            window.dispatchEvent(
              new CustomEvent('chat-title-updated', {
                detail: { chatId: currentChatId, title: generatedTitle },
              })
            );
          }
        } catch (error) {
          console.error('Failed to generate/update chat title:', error);
        }
      } else if (isFirstMessage && receivedResponse && botId && currentChatId) {
        try {
          const titleResponse = await chatsApi.generateTitle(botId, currentChatId);
          const generatedTitle = titleResponse.title;
          if (generatedTitle) {
            await chatsApi.update(botId, currentChatId, { title: generatedTitle });
            window.dispatchEvent(
              new CustomEvent('chat-title-updated', {
                detail: { chatId: currentChatId, title: generatedTitle },
              })
            );
          }
        } catch (error) {
          console.error('Failed to generate/update chat title (fallback):', error);
        }
      }
      
      // 如果没有收到任何响应，移除空消息并显示错误
      setMessages(prev => {
        const hasContent = prev.some(msg => 
          msg.id === assistantMessageId && msg.content.trim()
        );
        if (!hasContent && !receivedResponse) {
          // 移除空消息
          return prev.filter(msg => msg.id !== assistantMessageId);
        }
        return prev;
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        if (assistantMessageId) {
          setMessages((prev) =>
            prev.filter((msg) => msg.id !== assistantMessageId || msg.content.trim())
          );
        }
        return;
      }
      console.error('Failed to send message:', error);
      
      // 移除空消息
      if (assistantMessageId) {
        setMessages((prev) => prev.filter((msg) => msg.id !== assistantMessageId));
      }
      
      // 显示错误消息
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，发送消息时出现错误。请稍后重试。',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      abortControllerRef.current = null;
      setIsLoading(false);
      // 注意：不要在这里清除 streamingMessageId
      // 它应该在收到 stop 信号或连接关闭时清除
      // 如果在这里清除，可能导致时间戳过早显示
    }
  }, [inputValue, isLoading, botId, messages, selectedModel, chatId, navigate]);

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      // 如果正在加载，不允许发送新消息
      if (!isLoading) {
        handleSend();
      }
    }
  };

  const handleInputChange = (value: string) => {
    setInputValue(value);
    const atIndex = value.lastIndexOf('@');
    if (atIndex === -1) {
      setShowCollectionDropdown(false);
      setMentionQuery('');
      return;
    }

    const query = value.slice(atIndex + 1);
    if (query.includes(' ')) {
      setShowCollectionDropdown(false);
      setMentionQuery('');
      return;
    }

    setMentionQuery(query);
    setShowCollectionDropdown(true);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape' && showCollectionDropdown) {
      e.preventDefault();
      setShowCollectionDropdown(false);
    }
  };

  const handleSelectCollection = (collectionId: string) => {
    setInputValue((prev) => {
      const atIndex = prev.lastIndexOf('@');
      if (atIndex === -1) return prev;
      return `${prev.slice(0, atIndex)}@${collectionId} `;
    });
    setShowCollectionDropdown(false);
  };

  const formatTimestamp = (date: Date) => {
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const handleCopy = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const renderMarkdownContent = (content: string, className = 'message-text message-markdown') => (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ className: codeClassName, children, ...props }) {
            const isMermaid = /language-mermaid/.test(codeClassName ?? '');
            const code = String(children ?? '').trim();
            if (isMermaid && code) {
              return <MermaidDiagram code={code} className="message-mermaid" />;
            }
            return (
              <code className={codeClassName} {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );

  const handleDeleteChat = useCallback(async (chatIdToDelete: string, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    
    if (deletingChatId || !chatIdToDelete || !botId) return;

    const chat = chatList.find(c => c.id === chatIdToDelete);
    const chatTitle = chat?.title || `Chat ${chatIdToDelete}`;
    
    const confirmed = window.confirm(
      `确定要删除 "${chatTitle}" 吗？此操作无法撤销。`
    );
    
    if (!confirmed) return;

    try {
      setDeletingChatId(chatIdToDelete);
      await chatsApi.delete(botId, chatIdToDelete);
      
      // 如果删除的是当前正在查看的聊天，导航到新聊天页面
      if (chatIdToDelete === chatId) {
        navigate('/chats/new');
      }
      
      // 刷新聊天列表
      const data = await chatsApi.list(botId);
      setChatList(data.items || []);
    } catch (error) {
      console.error('Failed to delete chat:', error);
      alert('删除失败，请重试。');
    } finally {
      setDeletingChatId(null);
    }
  }, [botId, chatList, chatId, navigate]);

  const formatRelativeTime = (dateString?: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'JUST NOW';
    if (diffMins < 60) return `${diffMins} MIN${diffMins > 1 ? 'S' : ''} AGO`;
    if (diffHours < 24) return `${diffHours} HOUR${diffHours > 1 ? 'S' : ''} AGO`;
    if (diffDays === 1) return 'YESTERDAY';
    if (diffDays < 7) return `${diffDays} DAYS AGO`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const groupChatsByDate = (chats: Chat[]) => {
    const groups: { [key: string]: Chat[] } = {};
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    chats.forEach(chat => {
      if (!chat.updated) {
        groups['OTHER'] = groups['OTHER'] || [];
        groups['OTHER'].push(chat);
        return;
      }

      const chatDate = new Date(chat.updated);
      const chatDateOnly = new Date(chatDate.getFullYear(), chatDate.getMonth(), chatDate.getDate());

      if (chatDateOnly.getTime() === today.getTime()) {
        groups['TODAY'] = groups['TODAY'] || [];
        groups['TODAY'].push(chat);
      } else if (chatDateOnly.getTime() === yesterday.getTime()) {
        groups['YESTERDAY'] = groups['YESTERDAY'] || [];
        groups['YESTERDAY'].push(chat);
      } else {
        groups['OTHER'] = groups['OTHER'] || [];
        groups['OTHER'].push(chat);
      }
    });

    return groups;
  };

  // 确定显示的标题：优先使用当前会话标题，否则使用默认值
  const displayTitle = chatId === 'new' || !chatId 
    ? 'New chat' 
    : currentChatTitle || 'Chat';

  // 只在本次会话没有消息时显示欢迎内容
  // 只要消息列表不为空，就隐藏欢迎内容；否则在不在加载中时显示
  const isNewChat = messages.length === 0 && !isLoading && !loadingHistory;

  const filteredCollections = collections.filter((collection) => {
    const idMatch = collection.id?.toLowerCase().includes(mentionQuery.toLowerCase());
    const titleMatch = collection.title?.toLowerCase().includes(mentionQuery.toLowerCase());
    return idMatch || titleMatch;
  });

  const renderMentionDropdown = () => {
    if (!showCollectionDropdown) return null;
    return (
      <div className="collection-mention-dropdown">
        <div className="collection-mention-header">
          <span className="collection-mention-icon">@</span>
        </div>
        <div className="collection-mention-list">
          {collectionsLoading ? (
            <div className="collection-mention-item muted">加载集合中...</div>
          ) : filteredCollections.length > 0 ? (
            filteredCollections.map((collection) => {
              const primaryText = collection.title || collection.id || '';
              const secondaryText = collection.title ? collection.id : '';
              return (
                <button
                  key={collection.id}
                  className="collection-mention-item"
                  onClick={() => collection.id && handleSelectCollection(collection.id)}
                >
                  <span className="collection-mention-primary">{primaryText}</span>
                  {secondaryText && (
                    <span className="collection-mention-secondary">{secondaryText}</span>
                  )}
                </button>
              );
            })
          ) : (
            <div className="collection-mention-item muted">未找到集合</div>
          )}
        </div>
      </div>
    );
  };

  const renderInputContainer = (extraClassName?: string) => (
    <div className={`chats-input-container${extraClassName ? ` ${extraClassName}` : ''}`}>
      <div className="chats-input-wrapper" ref={mentionDropdownRef}>
        <input
          type="text"
          className="chats-input"
          placeholder="Type @ to mention a collection..."
          value={inputValue}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyPress={handleKeyPress}
          onKeyDown={handleInputKeyDown}
          disabled={isLoading}
        />
        {renderMentionDropdown()}
      </div>
      <div className="input-right-actions">
        <div className="input-left-actions">
          <button className="input-action-btn" title="Attachments">
            <Paperclip size={18} />
          </button>
          <button
            type="button"
            className={`input-action-btn${webSearchEnabled ? ' active' : ''}`}
            title={webSearchEnabled ? 'Web search on' : 'Web search'}
            onClick={() => setWebSearchEnabled(prev => !prev)}
          >
            <Globe size={18} />
          </button>
        </div>
        <div className="model-selector" ref={modelDropdownRef}>
          <button
            className="model-selector-btn"
            onClick={() => setShowModelDropdown(!showModelDropdown)}
            disabled={modelsLoading || availableModels.length === 0}
            title={modelsLoading ? 'Loading models...' : availableModels.length === 0 ? 'No models available' : 'Select model'}
          >
            <span className="model-name">
              {modelsLoading ? 'Loading...' : selectedModel?.model || 'Select model'}
            </span>
            <ChevronDown size={16} className={showModelDropdown ? 'rotated' : ''} />
          </button>
          {showModelDropdown && (
            <div className="model-dropdown">
              {modelsLoading ? (
                <div className="model-option" style={{ fontStyle: 'italic', opacity: 0.7 }}>
                  Loading models...
                </div>
              ) : availableModels.length > 0 ? (
                availableModels.map((model) => (
                  <button
                    key={getModelKey(model)}
                    className={`model-option ${
                      selectedModel && getModelKey(selectedModel) === getModelKey(model)
                        ? 'selected'
                        : ''
                    }`}
                    onClick={() => {
                      setSelectedModel(model);
                      setShowModelDropdown(false);
                    }}
                  >
                    {model.model}
                  </button>
                ))
              ) : (
                <div className="model-option" style={{ fontStyle: 'italic', opacity: 0.7 }}>
                  暂无可用模型
                </div>
              )}
            </div>
          )}
        </div>
        <button
          className="send-button"
          onClick={isLoading ? handleStop : handleSend}
          disabled={!isLoading && (!inputValue.trim() || !botId || !selectedModel?.model)}
          title={
            !botId
              ? 'Waiting for Bot...'
              : !selectedModel?.model
              ? 'Select a model...'
              : isLoading
              ? 'Stop generating'
              : 'Send message'
          }
        >
          {isLoading ? <Square size={18} /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );

  return (
    <div className="chats-page">
      <div className="chats-layout"><div className="chats-main">
          <div className="chats-header">
            <h1 className="chats-title">{displayTitle}</h1>
          </div>

          {isNewChat ? (
            <div className="chats-welcome-container">
              <div className="chats-welcome-content">
                <h2 className="welcome-title">Hi, I'm SuperRAG.</h2>
                <p className="welcome-description">
                  SuperRAG is a production-ready RAG platform that combines graph, vector, and full-text search for hybrid retrieval, knowledge management, and enterprise AI applications.
                </p>
              </div>
              {renderInputContainer('chats-input-centered')}
            </div>
          ) : (
            <div className="chats-agui-layout">
              <div className="chats-agui-chat">
                <div className="chats-messages">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'}`}
                    >
                      <div className="message-content">
                        <div className="message-bubble">
                          {message.role === 'assistant' ? (
                            (() => {
                              const trace = assistantTraces[message.id];
                              const toolRuns = trace
                                ? Object.values(trace.tools).sort((a, b) => a.createdAt - b.createdAt)
                                : [];
                              const activities = trace
                                ? Object.values(trace.activities).sort((a, b) => a.createdAt - b.createdAt)
                                : [];
                              const hasReasoning = Boolean(trace?.reasoning?.trim());
                              const hasTools = toolRuns.length > 0;
                              const hasActivities = activities.length > 0;
                              const hasFinalContent = Boolean(message.content.trim());

                              return (
                                <div className="assistant-response-stack">
                                  {hasReasoning && (
                                    <div className="trace-thinking">
                                      <div className="trace-thinking-icon">
                                        <Brain size={14} />
                                      </div>
                                      <div className="trace-thinking-body">
                                        {renderMarkdownContent(
                                          trace?.reasoning ?? '',
                                          'message-text message-markdown trace-thinking-text'
                                        )}
                                      </div>
                                    </div>
                                  )}

                                  {hasTools && toolRuns.map((tool) => (
                                    <details key={tool.tool_call_id} className="trace-tool">
                                      <summary className="trace-tool-header">
                                        <span className={`trace-tool-status-icon ${tool.status}`}>
                                          {tool.status === 'completed'
                                            ? <Check size={14} />
                                            : <Loader2 size={14} className="spinning" />}
                                        </span>
                                        <span className="trace-tool-label">Called tool</span>
                                        <code className="trace-tool-name">{tool.tool_call_name || 'tool'}</code>
                                        <span className="trace-tool-toggle">
                                          <ChevronRight size={16} className="trace-tool-chevron" />
                                        </span>
                                      </summary>
                                      <div className="trace-tool-body">
                                        {tool.args && (
                                          <div className="trace-tool-section">
                                            <div className="trace-tool-section-label">INPUT 输入</div>
                                            <pre className="trace-tool-code">{(() => {
                                              try { return JSON.stringify(JSON.parse(tool.args), null, 2); }
                                              catch { return tool.args; }
                                            })()}</pre>
                                          </div>
                                        )}
                                        {tool.content && (
                                          <div className="trace-tool-section">
                                            <div className="trace-tool-section-label">
                                              OUTPUT 输出
                                              <Info size={12} className="trace-tool-info-icon" />
                                            </div>
                                            <pre className="trace-tool-code">{tool.content}</pre>
                                          </div>
                                        )}
                                      </div>
                                    </details>
                                  ))}

                                  {hasActivities && activities.map((activity) => (
                                    <details key={activity.key} className="trace-tool">
                                      <summary className="trace-tool-header">
                                        <span className="trace-tool-status-icon completed">
                                          <Info size={14} />
                                        </span>
                                        <span className="trace-tool-label">{activity.activityType}</span>
                                        <span className="trace-tool-toggle">
                                          <ChevronRight size={16} className="trace-tool-chevron" />
                                        </span>
                                      </summary>
                                      <div className="trace-tool-body">
                                        <pre className="trace-tool-code">{activity.content}</pre>
                                      </div>
                                    </details>
                                  ))}

                                  {hasFinalContent && renderMarkdownContent(
                                    message.content,
                                    'message-text message-markdown trace-final-body'
                                  )}
                                </div>
                              );
                            })()
                          ) : (
                            <p className="message-text">{message.content}</p>
                          )}
                        </div>
                        <div className="message-footer">
                          {message.role === 'assistant' && (streamingMessageId || !message.content.trim()) ? null : (
                            <span className="message-timestamp">
                              {formatTimestamp(message.timestamp)}
                            </span>
                          )}
                          {message.role === 'assistant' && message.content.trim() && !streamingMessageId && (
                            <div className="message-actions">
                              <button
                                className="message-action-btn"
                                title="Like"
                                onClick={() => {}}
                              >
                                <ThumbsUp size={16} />
                              </button>
                              <button
                                className="message-action-btn"
                                title="Dislike"
                                onClick={() => {}}
                              >
                                <ThumbsDown size={16} />
                              </button>
                              <button
                                className="message-action-btn"
                                title="Copy"
                                onClick={() => handleCopy(message.content)}
                              >
                                <Copy size={16} />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>

                {renderInputContainer()}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
