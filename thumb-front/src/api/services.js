import { del, get, post, put, pythonAgentRequest } from './request'

export const userApi = {
  login(payload) {
    return post('/login', payload)
  },

  register(payload) {
    return post('/register', payload)
  },

  logout() {
    return post('/logout')
  },

  createAgentToken() {
    return post('/agent/token')
  },

  getProfile() {
    return get('/user/profile')
  },

  updateProfile(payload) {
    return put('/user/profile', payload)
  },
}

export const blogApi = {
  getList() {
    return get('/blog/all')
  },

  getMine() {
    return get('/blog/my')
  },

  getDetail(blogId) {
    return get(`/blog/${blogId}`)
  },

  create(payload) {
    return post('/blog/create', payload)
  },

  update(blogId, payload) {
    return put(`/blog/${blogId}`, payload)
  },

  remove(blogId) {
    return del(`/blog/${blogId}`)
  },

  page(params) {
    return get('/blog/page', params)
  },

  pageMine(params) {
    return get('/blog/my/page', params)
  },
}

export const thumbApi = {
  doThumb(blogId) {
    return post('/thumb/do', { blogId: String(blogId) })
  },

  undoThumb(blogId) {
    return post('/thumb/undo', { blogId: String(blogId) })
  },
}

export const commentApi = {
  create(payload) {
    return post('/comment', payload)
  },

  reply(commentId, content) {
    return post(`/comment/${commentId}/replies`, { content })
  },

  listByBlog(blogId) {
    return get(`/comment/blog/${blogId}`)
  },

  pageByBlog(blogId, params) {
    return get(`/comment/blog/${blogId}/page`, params)
  },

  remove(commentId) {
    return del(`/comment/${commentId}`)
  },

  count(blogId) {
    return get(`/comment/count/${blogId}`)
  },
}

export const adminApi = {
  overview() {
    return get('/admin/overview')
  },

  pageUsers(params) {
    return get('/admin/users/page', params)
  },

  updateUserEnabled(userId, enabled) {
    return put(`/admin/users/${userId}/enabled`, {}, { enabled })
  },

  updateUserRole(userId, role) {
    return put(`/admin/users/${userId}/role`, {}, { role })
  },

  removeUser(userId) {
    return del(`/admin/users/${userId}`)
  },

  pageBlogs(params) {
    return get('/admin/blogs/page', params)
  },

  updateBlogAuditStatus(blogId, auditStatus) {
    return put(`/admin/blogs/${blogId}/audit-status`, {}, { auditStatus })
  },

  updateBlogEmbeddingStatus(blogId, embeddingStatus) {
    return put(
      `/admin/blogs/${blogId}/embedding-status`,
      {},
      { embeddingStatus }
    )
  },

  removeBlog(blogId) {
    return del(`/admin/blogs/${blogId}`)
  },

  pageRagLogs(params) {
    return get('/admin/rag/logs/page', params)
  },

  pageAnalyticsLogs(params) {
    return get('/admin/analytics/logs/page', params)
  },

  getRagLog(logId) {
    return get(`/admin/rag/logs/${logId}`)
  },

  getAnalyticsLog(logId) {
    return get(`/admin/analytics/logs/${logId}`)
  },
}

export const ragLogApi = {
  page(params) {
    return get('/agent/rag/logs/page', params)
  },
}

export const analyticsLogApi = {
  page(params) {
    return get('/agent/analytics/logs/page', params)
  },
}

export const agentApi = {
  async streamChat(payload, onEvent) {
    const response = await fetch('/py-agent/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('aiToken') || ''}`,
      },
      body: JSON.stringify(payload),
    })
    if (!response.ok || !response.body) {
      const body = await response.json().catch(() => ({}))
      throw new Error(
        body.detail || body.message || `Agent 请求失败（${response.status}）`
      )
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder
        .decode(value || new Uint8Array(), { stream: !done })
        .replace(/\r\n/g, '\n')
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        const event = block.match(/^event:\s*(.+)$/m)?.[1] || 'message'
        const raw = block.match(/^data:\s*(.+)$/m)?.[1]
        if (!raw) continue
        onEvent(event, JSON.parse(raw))
      }
      if (done) break
    }
  },

  chat(payload) {
    return pythonAgentRequest.post('/chat', payload)
  },

  askRag(payload) {
    return pythonAgentRequest.post('/rag/ask', payload)
  },

  analytics(payload) {
    return pythonAgentRequest.post('/analytics/query', payload)
  },

  async streamAnalytics(payload, onEvent) {
    const response = await fetch('/py-agent/analytics/query/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('aiToken') || ''}`,
      },
      body: JSON.stringify(payload),
    })
    if (!response.ok || !response.body) {
      const body = await response.json().catch(() => ({}))
      throw new Error(
        body.detail || body.message || `运营助手请求失败（${response.status}）`
      )
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder
        .decode(value || new Uint8Array(), { stream: !done })
        .replace(/\r\n/g, '\n')
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        const event = block.match(/^event:\s*(.+)$/m)?.[1] || 'message'
        const raw = block.match(/^data:\s*(.+)$/m)?.[1]
        if (!raw) continue
        onEvent(event, JSON.parse(raw))
      }
      if (done) break
    }
  },

  analyticsLogsPage(params) {
    return pythonAgentRequest.get('/analytics/logs/page', { params })
  },

  operationsAnalyze(payload) {
    return pythonAgentRequest.post('/operations/analyze', payload)
  },

  dailyReports(params) {
    return pythonAgentRequest.get('/operations/daily-reports', { params })
  },

  dailyReportDetail(reportDate) {
    return pythonAgentRequest.get(`/operations/daily-reports/${reportDate}`)
  },
}
