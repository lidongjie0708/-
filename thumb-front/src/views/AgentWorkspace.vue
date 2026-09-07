<template>
  <main class="agent-page">
    <div class="container-custom">
      <header class="nav-bar">
        <router-link class="brand" to="/"><span>赞</span>Yu Like</router-link>
        <nav class="nav-actions">
          <router-link class="btn btn-outline" to="/">博客首页</router-link>
          <LoginBadge />
        </nav>
      </header>

      <section class="hero surface">
        <div>
          <p>AI Agent 工作台</p>
          <h1>RAG 问答与运营分析</h1>
          <span>前端先向 Java 获取短期 AI token，再调用 Python Agent 服务。</span>
        </div>
        <button class="btn btn-primary" type="button" :disabled="!canRun" @click="runAgent">
          {{ loading ? '运行中...' : activeMode === 'rag' ? '运行 RAG Agent' : '运行运营 Agent' }}
        </button>
      </section>

      <section v-if="!userStore.isLoggedIn" class="notice surface">
        <div>
          <strong>请先登录</strong>
          <span>Agent 接口需要登录后的 JWT 和 AI token。</span>
        </div>
        <router-link class="btn btn-primary" to="/login">去登录</router-link>
      </section>

      <section class="mode-grid">
        <button class="mode-card surface" :class="{ active: activeMode === 'rag' }" type="button" @click="activeMode = 'rag'">
          <span class="mode-kicker">RAG Agent</span>
          <strong>博客知识库问答</strong>
          <small>基于已同步的博客内容进行检索增强问答，适合问系统知识、文章内容、技术方案。</small>
        </button>
        <button v-if="isAdmin" class="mode-card surface" :class="{ active: activeMode === 'analytics' }" type="button" @click="activeMode = 'analytics'">
          <span class="mode-kicker">运营 Agent</span>
          <strong>运营数据分析</strong>
          <small>面向管理员/运营问题，生成安全 SQL、查询数据并输出分析报告。</small>
        </button>
      </section>

      <section class="workspace">
        <aside class="panel surface">
          <template v-if="activeMode === 'rag'">
            <label for="ragQuestion">RAG 问题</label>
            <textarea
              id="ragQuestion"
              v-model.trim="ragQuestion"
              class="input-control textarea"
              placeholder="例如：这套博客系统的点赞功能是怎么设计的？"
            ></textarea>
            <label for="sessionId">会话 ID，可选</label>
            <input id="sessionId" v-model.trim="sessionId" class="input-control" placeholder="用于多轮问答记忆，例如 demo-session" />
            <div class="hint">普通用户只查 PUBLIC 内容；管理员会同时查 PUBLIC 和 PRIVATE。</div>
          </template>

          <template v-else>
            <label for="analyticsQuestion">运营分析问题</label>
            <textarea
              id="analyticsQuestion"
              v-model.trim="analyticsQuestion"
              class="input-control textarea"
              placeholder="例如：点赞最多的文章有哪些？最近用户活跃情况怎么样？"
            ></textarea>
            <div class="hint">运营分析仅管理员可用；Python 端会再次校验 ADMIN 角色并做 SQL 安全检查。</div>
          </template>
        </aside>

        <section class="result surface">
          <div class="result-head">
            <div>
              <h2>{{ activeMode === 'rag' ? 'RAG Agent 结果' : '运营 Agent 结果' }}</h2>
              <span>{{ activeMode === 'rag' ? '/api/agent/rag/ask' : '/api/agent/analytics/query' }}</span>
            </div>
            <button class="btn btn-outline" type="button" :disabled="!resultText" @click="copyResult">复制</button>
          </div>

          <div v-if="error" class="error-message">{{ error }}</div>
          <pre v-if="resultText">{{ resultText }}</pre>
          <div v-else class="empty">填写问题后运行 Agent，响应会显示在这里。</div>
        </section>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue';
import LoginBadge from '../components/common/LoginBadge.vue';
import { agentApi } from '../api/services';
import { useUserStore } from '../stores/user';

const userStore = useUserStore();
const activeMode = ref('rag');
const ragQuestion = ref('');
const analyticsQuestion = ref('');
const sessionId = ref('');
const loading = ref(false);
const error = ref('');
const result = ref(null);

const currentQuestion = computed(() => (activeMode.value === 'rag' ? ragQuestion.value : analyticsQuestion.value));
const isAdmin = computed(() => String(userStore.role || '').toUpperCase() === 'ADMIN');
const canRun = computed(() => {
  if (!userStore.isLoggedIn || loading.value || currentQuestion.value.trim().length === 0) return false;
  if (activeMode.value === 'analytics') return isAdmin.value;
  return true;
});
const resultText = computed(() => (result.value ? JSON.stringify(result.value, null, 2) : ''));

async function runAgent() {
  if (!canRun.value) return;
  if (activeMode.value === 'analytics' && !isAdmin.value) {
    error.value = '运营 Agent 仅管理员可用';
    return;
  }
  error.value = '';
  result.value = null;
  loading.value = true;

  try {
    await userStore.ensureAgentToken();
    const role = userStore.role || 'USER';
    const userId = userStore.getUserId;
    const response =
      activeMode.value === 'rag'
        ? await agentApi.askRag({
            question: ragQuestion.value,
            sessionId: sessionId.value || undefined,
            userId,
            role,
            visibleScopes: role === 'ADMIN' ? ['PUBLIC', 'PRIVATE'] : ['PUBLIC'],
          })
        : await agentApi.analytics({
            question: analyticsQuestion.value,
            userId,
            role,
            sessionId: sessionId.value || undefined,
          });

    result.value = response.data;
  } catch (err) {
    error.value = err.response?.data?.message || err.response?.data?.detail || err.message || 'Agent 调用失败';
  } finally {
    loading.value = false;
  }
}

async function copyResult() {
  await navigator.clipboard?.writeText(resultText.value);
}
</script>

<style scoped>
.agent-page {
  min-height: 100vh;
  background: #f7f8fb;
  padding-bottom: 3rem;
}

.nav-bar,
.nav-actions,
.hero,
.result-head {
  display: flex;
  align-items: center;
}

.nav-bar {
  justify-content: space-between;
  padding: 1rem 0;
}

.nav-actions {
  gap: 0.75rem;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  font-weight: 900;
}

.brand span {
  display: grid;
  width: 2.15rem;
  height: 2.15rem;
  place-items: center;
  border-radius: 0.55rem;
  background: #0f766e;
  color: #fff;
}

.hero {
  justify-content: space-between;
  gap: 1rem;
  border-radius: 0.5rem;
  padding: 1.5rem;
}

.hero p,
.mode-kicker {
  margin: 0 0 0.5rem;
  color: #0f766e;
  font-size: 0.85rem;
  font-weight: 900;
}

.hero h1 {
  margin: 0;
  color: #172033;
  font-size: clamp(1.8rem, 4vw, 3.2rem);
  font-weight: 950;
  letter-spacing: 0;
}

.hero span,
.hint,
.result-head span {
  color: #64748b;
}

.hero span {
  display: block;
  margin-top: 0.55rem;
}

.notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1rem;
  border-radius: 0.5rem;
  padding: 1rem;
}

.notice div {
  display: grid;
  gap: 0.25rem;
}

.mode-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.mode-card {
  display: grid;
  gap: 0.55rem;
  border-radius: 0.5rem;
  padding: 1rem;
  text-align: left;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.mode-card:hover,
.mode-card.active {
  border-color: #0f766e;
  box-shadow: 0 16px 38px rgba(15, 23, 42, 0.1);
  transform: translateY(-2px);
}

.mode-card strong {
  color: #172033;
  font-size: 1.12rem;
}

.mode-card small {
  color: #64748b;
  line-height: 1.65;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(20rem, 26rem) minmax(0, 1fr);
  gap: 1rem;
  margin-top: 1rem;
}

.panel,
.result {
  border-radius: 0.5rem;
  padding: 1rem;
}

.panel {
  display: grid;
  gap: 0.85rem;
  align-content: start;
}

label {
  color: #334155;
  font-size: 0.9rem;
  font-weight: 800;
}

.textarea {
  min-height: 11rem;
  resize: vertical;
}

.hint {
  border-radius: 0.45rem;
  background: #f1f5f9;
  padding: 0.75rem;
  font-size: 0.85rem;
  line-height: 1.6;
}

.result {
  min-height: 32rem;
}

.result-head {
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.result h2 {
  margin: 0 0 0.25rem;
  color: #172033;
  font-size: 1.25rem;
}

pre {
  min-height: 26rem;
  overflow: auto;
  border-radius: 0.45rem;
  background: #0f172a;
  color: #d1fae5;
  padding: 1rem;
  line-height: 1.6;
  white-space: pre-wrap;
}

.empty {
  display: grid;
  min-height: 26rem;
  place-items: center;
  border: 1px dashed #cbd5e1;
  border-radius: 0.45rem;
  color: #64748b;
  text-align: center;
}

.error-message {
  margin-bottom: 1rem;
  border-radius: 0.45rem;
  background: #fef2f2;
  color: #b91c1c;
  padding: 0.75rem;
  font-weight: 700;
}

@media (max-width: 860px) {
  .hero,
  .notice,
  .nav-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .mode-grid,
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>
