<template>
  <main class="page">
    <AppHeader />
    <div class="container-custom admin-wrap">
      <section class="hero surface">
        <div>
          <p>ADMIN CONSOLE</p>
          <h1>系统管理后台</h1>
          <span>用户、文章审核与 Agent 运行日志统一管理</span>
        </div>
        <button class="btn btn-primary" @click="refresh">刷新数据</button>
      </section>
      <nav class="tabs">
        <button
          v-for="item in tabs"
          :key="item.key"
          :class="{ active: tab === item.key }"
          @click="tab = item.key"
        >
          {{ item.label }}
        </button>
      </nav>
      <div v-if="error" class="error">{{ error }}</div>

      <section v-if="tab === 'overview'" class="metrics">
        <article v-for="(value, key) in overview" :key="key" class="surface">
          <span>{{ labels[key] || key }}</span
          ><strong>{{ value }}</strong>
        </article>
      </section>

      <section v-else-if="tab === 'users'" class="panel surface">
        <div class="panel-head">
          <h2>用户管理</h2>
          <input
            v-model="filters.username"
            class="input-control search"
            placeholder="搜索用户名"
            @keyup.enter="loadUsers"
          />
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>用户</th>
                <th>邮箱</th>
                <th>角色</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td>{{ u.id }}</td>
                <td>
                  {{ u.username }}
                  <small v-if="String(u.id) === String(userStore.getUserId)"
                    >当前账号</small
                  >
                </td>
                <td>{{ u.email }}</td>
                <td>
                  <select
                    :value="u.role"
                    @change="setRole(u, $event.target.value)"
                  >
                    <option>USER</option>
                    <option>ADMIN</option>
                  </select>
                </td>
                <td>{{ u.enabled ? '启用' : '禁用' }}</td>
                <td class="actions">
                  <button @click="toggleUser(u)">
                    {{ u.enabled ? '禁用' : '启用' }}</button
                  ><button
                    class="danger"
                    :disabled="String(u.id) === String(userStore.getUserId)"
                    @click="deleteUser(u)"
                  >
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else-if="tab === 'blogs'" class="panel surface">
        <div class="panel-head">
          <h2>文章管理</h2>
          <input
            v-model="filters.title"
            class="input-control search"
            placeholder="搜索标题"
            @keyup.enter="loadBlogs"
          />
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>标题</th>
                <th>作者ID</th>
                <th>审核</th>
                <th>向量化</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in blogs" :key="b.id">
                <td>{{ b.id }}</td>
                <td>
                  <router-link :to="`/blog/${b.id}`">{{ b.title }}</router-link>
                </td>
                <td>{{ b.userId }}</td>
                <td>
                  <select
                    :value="b.auditStatus ?? 0"
                    @change="setAudit(b, $event.target.value)"
                  >
                    <option value="0">待审核</option>
                    <option value="1">通过</option>
                    <option value="2">拒绝</option>
                  </select>
                </td>
                <td>
                  <select
                    :value="b.embeddingStatus ?? 0"
                    @change="setEmbedding(b, $event.target.value)"
                  >
                    <option value="0">未处理</option>
                    <option value="1">处理中</option>
                    <option value="2">完成</option>
                    <option value="3">失败</option>
                  </select>
                </td>
                <td>
                  <button class="danger" @click="deleteBlog(b)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else class="panel surface">
        <div class="panel-head">
          <h2>{{ tab === 'ragLogs' ? 'RAG 观测日志' : '运营分析日志' }}</h2>
          <div class="log-filters">
            <input v-model.trim="filters.logQuestion" class="input-control" placeholder="问题关键词" />
            <input v-model.number="filters.logUserId" class="input-control" type="number" placeholder="用户 ID" />
            <input v-model="filters.createdFrom" class="input-control" type="datetime-local" />
            <button class="btn btn-outline" @click="loadLogs">筛选</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>问题</th>
                <th>用户</th>
                <th>{{ tab === 'ragLogs' ? '引用' : '状态' }}</th>
                <th>时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs" :key="log.id">
                <td>{{ log.id }}</td>
                <td class="question">{{ log.question }}</td>
                <td>{{ log.userId || '-' }}</td>
                <td>
                  {{
                    tab === 'ragLogs'
                      ? log.hasCitations
                        ? '有'
                        : '无'
                      : log.status || '-'
                  }}
                </td>
                <td>{{ formatDate(log.createdAt) }}</td>
                <td><button @click="showLogDetail(log.id)">详情</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <pre v-if="selectedLog" class="log-detail">{{ JSON.stringify(selectedLog, null, 2) }}</pre>
      </section>
    </div>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import AppHeader from '../components/common/AppHeader.vue'
import { adminApi } from '../api/services'
import { formatDate } from '../utils'
import { useUserStore } from '../stores/user'
const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'users', label: '用户管理' },
  { key: 'blogs', label: '文章管理' },
  { key: 'ragLogs', label: 'RAG 日志' },
  { key: 'analyticsLogs', label: '运营日志' },
]
const labels = {
  userCount: '用户总数',
  enabledUserCount: '启用用户',
  blogCount: '文章总数',
  pendingAuditBlogCount: '待审核文章',
  embeddedBlogCount: '已向量化',
  ragLogCount: 'RAG 调用',
  analyticsLogCount: '运营分析',
  failedAnalyticsLogCount: '分析失败',
}
const tab = ref('overview'),
  overview = ref({}),
  users = ref([]),
  blogs = ref([]),
  logs = ref([]),
  selectedLog = ref(null),
  error = ref('')
const userStore = useUserStore()
const filters = reactive({ username: '', title: '', logQuestion: '', logUserId: null, createdFrom: '' })
const unwrap = (r) => r.data?.data || {}
async function loadOverview() {
  overview.value = unwrap(await adminApi.overview())
}
async function loadUsers() {
  users.value =
    unwrap(
      await adminApi.pageUsers({
        pageNum: 1,
        pageSize: 100,
        username: filters.username,
      })
    ).records || []
}
async function loadBlogs() {
  blogs.value =
    unwrap(
      await adminApi.pageBlogs({
        pageNum: 1,
        pageSize: 100,
        title: filters.title,
      })
    ).records || []
}
async function loadLogs() {
  const params = {
    pageNum: 1,
    pageSize: 100,
    question: filters.logQuestion || undefined,
    userId: filters.logUserId || undefined,
    createdFrom: filters.createdFrom ? new Date(filters.createdFrom).toISOString() : undefined,
  }
  const r =
    tab.value === 'ragLogs'
      ? await adminApi.pageRagLogs(params)
      : await adminApi.pageAnalyticsLogs(params)
  logs.value = unwrap(r).records || []
  selectedLog.value = null
}
async function showLogDetail(logId) {
  const response =
    tab.value === 'ragLogs'
      ? await adminApi.getRagLog(logId)
      : await adminApi.getAnalyticsLog(logId)
  selectedLog.value = unwrap(response)
}
async function refresh() {
  error.value = ''
  try {
    if (tab.value === 'overview') await loadOverview()
    else if (tab.value === 'users') await loadUsers()
    else if (tab.value === 'blogs') await loadBlogs()
    else await loadLogs()
  } catch (e) {
    error.value = e.response?.data?.message || '数据加载失败'
  }
}
async function setRole(u, role) {
  if (!confirm(`确定将 ${u.username} 的角色修改为 ${role}？`)) {
    await loadUsers()
    return
  }
  try {
    await adminApi.updateUserRole(u.id, role)
    u.role = role
  } catch (e) {
    error.value = e.response?.data?.message || '角色更新失败'
    await loadUsers()
  }
}
async function toggleUser(u) {
  try {
    const enabled = u.enabled ? 0 : 1
    await adminApi.updateUserEnabled(u.id, enabled)
    u.enabled = enabled
  } catch (e) {
    error.value = e.response?.data?.message || '状态更新失败'
  }
}
async function deleteUser(u) {
  if (!confirm(`确定删除用户 ${u.username}？`)) return
  try {
    await adminApi.removeUser(u.id)
    await loadUsers()
  } catch (e) {
    error.value = e.response?.data?.message || '删除失败'
  }
}
async function setAudit(b, v) {
  await adminApi.updateBlogAuditStatus(b.id, Number(v))
  b.auditStatus = Number(v)
}
async function setEmbedding(b, v) {
  await adminApi.updateBlogEmbeddingStatus(b.id, Number(v))
  b.embeddingStatus = Number(v)
}
async function deleteBlog(b) {
  if (!confirm(`确定删除《${b.title}》？`)) return
  await adminApi.removeBlog(b.id)
  await loadBlogs()
}
watch(tab, refresh)
onMounted(refresh)
</script>

<style scoped>
.admin-wrap {
  padding-top: 24px;
}
.page {
  min-height: 100vh;
  padding-bottom: 3rem;
}
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-radius: 0.75rem;
}
.hero p,
.hero h1 {
  margin: 0;
}
.hero p {
  color: #0f766e;
  font-weight: 950;
}
.hero h1 {
  margin: 0.3rem 0;
  font-size: 2.2rem;
}
.hero span {
  color: #64748b;
}
.tabs {
  display: flex;
  gap: 0.5rem;
  overflow: auto;
  margin: 1.2rem 0;
}
.tabs button {
  white-space: nowrap;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  background: white;
  padding: 0.65rem 1rem;
  font-weight: 800;
  color: #475569;
}
.tabs button.active {
  border-color: #0f766e;
  background: #0f766e;
  color: white;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}
.metrics article {
  display: grid;
  gap: 0.6rem;
  border-radius: 0.65rem;
  padding: 1.2rem;
}
.metrics span {
  color: #64748b;
}
.metrics strong {
  font-size: 2rem;
}
.panel {
  border-radius: 0.65rem;
  padding: 1rem;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.log-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.log-filters .input-control {
  width: 10rem;
}
.log-detail {
  overflow: auto;
  max-height: 32rem;
  margin-top: 1rem;
  border-radius: 0.5rem;
  background: #0f172a;
  padding: 1rem;
  color: #e2e8f0;
  white-space: pre-wrap;
}
.panel-head h2 {
  margin: 0;
}
.search {
  max-width: 20rem;
}
.table-wrap {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.8rem;
  text-align: left;
  font-size: 0.9rem;
}
th {
  color: #64748b;
}
td select {
  border: 1px solid #cbd5e1;
  border-radius: 0.35rem;
  padding: 0.35rem;
}
.actions {
  display: flex;
  gap: 0.6rem;
}
.actions button,
td > button {
  border: 0;
  background: #f1f5f9;
  border-radius: 0.35rem;
  padding: 0.4rem 0.6rem;
  font-weight: 800;
}
.danger {
  color: #dc2626 !important;
}
.question {
  min-width: 18rem;
  max-width: 34rem;
}
.error {
  margin-bottom: 1rem;
  background: #fef2f2;
  color: #b91c1c;
  padding: 1rem;
  border-radius: 0.5rem;
}
@media (max-width: 850px) {
  .metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  .hero {
    align-items: flex-start;
    flex-direction: column;
    gap: 1rem;
  }
}
@media (max-width: 500px) {
  .metrics {
    grid-template-columns: 1fr;
  }
}
</style>
