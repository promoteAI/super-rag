# 后端 API 检测文档

## Collections API 端点

基于后端代码检测，以下是可用的 Collections API 端点：

### 基础路径
所有 API 端点前缀为：`/api/v1`

### 1. 获取集合列表
- **端点**: `GET /api/v1/collections`
- **参数**:
  - `page` (int, 默认: 1): 页码
  - `page_size` (int, 默认: 50): 每页数量
- **响应**: `CollectionViewList`
  ```typescript
  {
    items?: CollectionView[];
    pageResult?: {
      page_number?: number;
      page_size?: number;
      count?: number;
    };
  }
  ```

### 2. 获取单个集合
- **端点**: `GET /api/v1/collections/{collection_id}`
- **响应**: `Collection`

### 3. 创建集合
- **端点**: `POST /api/v1/collections`
- **请求体**: `CollectionCreate`
  ```typescript
  {
    title?: string;
    description?: string;
    type?: string;
    config?: any;
    source?: any;
  }
  ```
- **响应**: `Collection`

### 4. 更新集合
- **端点**: `PUT /api/v1/collections/{collection_id}`
- **请求体**: `CollectionUpdate`
- **响应**: `Collection`

### 5. 删除集合
- **端点**: `DELETE /api/v1/collections/{collection_id}`
- **响应**: `Collection`

### 6. 导入文档到集合
- **端点**: `POST /api/v1/collections/{collection_id}/documents`
- **请求**: 多文件上传 (`List[UploadFile]`)
- **响应**: `DocumentList`

### 7. 获取集合文档列表
- **端点**: `GET /api/v1/collections/{collection_id}/documents`
- **参数**:
  - `page` (int): 页码
  - `page_size` (int): 每页数量
  - `sort_by` (str): 排序字段
  - `sort_order` (str): 排序方向 (asc/desc)
  - `search` (str): 搜索关键词
- **响应**: 分页文档列表

### 8. 搜索集合
- **端点**: `POST /api/v1/collections/{collection_id}/searches`
- **请求体**: `SearchRequest`
- **响应**: `SearchResult`

## 数据模型

### CollectionView
```typescript
{
  id?: string;
  title?: string;
  description?: string;
  type?: string;
  status?: 'ACTIVE' | 'INACTIVE' | 'DELETED';
  created?: string;
  updated?: string;
  owner_user_id?: string;
}
```

### Collection
```typescript
{
  id?: string;
  title?: string;
  type?: string;
  description?: string;
  status?: 'ACTIVE' | 'INACTIVE' | 'DELETED';
  created?: string;
  updated?: string;
  is_published?: boolean;
  published_at?: string;
  config?: CollectionConfig;
  source?: CollectionSource;
}
```

## 认证

所有 API 端点都需要用户认证。当前实现使用 `default_user` 依赖注入。

## 前端集成

前端已实现以下功能：
- ✅ 集合列表展示
- ✅ 集合搜索（前端过滤）
- ✅ 创建新集合
- ✅ 删除集合
- ⏳ 编辑集合（UI已准备，待实现）
- ⏳ 查看集合详情（UI已准备，待实现）
- ⏳ 导入数据（UI已准备，待实现）
- ⏳ 与数据聊天（UI已准备，待实现）

## 注意事项

1. API 基础 URL 在开发模式下通过 Vite 代理配置为 `http://localhost:8000`
2. 生产环境需要配置正确的 API 基础 URL
3. 所有日期字段使用 ISO 8601 格式字符串
4. 分页从 1 开始（1-based）
