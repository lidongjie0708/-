<template>
  <main class="page">
    <AppHeader />
    <div class="container-custom agent-wrap">
      <section class="hero surface">
        <div>
          <p>AI ASSISTANT</p>
          <h1>一个入口，三种能力</h1>
          <span>普通聊天、博客知识库与运营分析在同一会话中协作。</span>
        </div>
        <div class="session-actions">
          <span class="session">会话 {{ sessionId.slice(-8) }}</span
          ><button class="btn btn-outline" @click="newSession">新建会话</button
          ><button
            v-if="messages.length"
            class="btn btn-soft"
            @click="messages = []"
          >
            清空消息
          </button>
        </div>
      </section>

      <section class="mode-bar surface">
        <button
          v-for="item in availableModes"
          :key="item.key"
          :class="{ active: mode === item.key }"
          @click="mode = item.key"
        >
          <strong>{{ item.label }}</strong
          ><small>{{ item.description }}</small>
        </button>
      </section>

      <section class="chat surface">
        <div ref="messagePanel" class="messages">
          <div v-if="!messages.length" class="welcome">
            <strong>今天想聊什么？</strong>
            <span>你可以直接提问，也可以明确选择知识库或运营分析模式。</span>
            <div>
              <button
                v-for="prompt in prompts"
                :key="prompt"
                @click="draft = prompt"
              >
                {{ prompt }}
              </button>
            </div>
          </div>
          <article
            v-for="item in messages"
            :key="item.id"
            :class="['message', item.role]"
          >
            <div class="bubble">
              <div class="meta">
                <strong>{{
                  item.role === 'user' ? '你' : modeLabel(item.mode)
                }}</strong
                ><span v-if="item.traceId"
                  >#{{ item.traceId.slice(0, 8) }}</span
                >
              </div>
              <p>{{ item.content }}</p>
              <div v-if="item.warning" class="warning">{{ item.warning }}</div>
              <div v-if="item.citations?.length" class="citations">
                <strong>引用来源</strong>
                <router-link
                  v-for="(citation, index) in item.citations"
                  :key="index"
                  :to="citation.articleId ? `/blog/${citation.articleId}` : '#'"
                >
                  [{{ index + 1 }}] {{ citation.title || '博客内容' }}
                  <small>{{
                    score(citation.rerankScore ?? citation.score)
                  }}</small>
                </router-link>
              </div>
              <div v-if="item.chart" class="analysis">
                <strong>分析结果</strong>
                <pre>{{ JSON.stringify(item.chart, null, 2) }}</pre>
              </div>
              <div v-if="item.suggestions?.length" class="suggestions">
                <button
                  v-for="suggestion in item.suggestions"
                  :key="suggestion"
                  @click="draft = suggestion"
                >
                  {{ suggestion }}
                </button>
              </div>
            </div>
          </article>
          <article v-if="loading" class="message assistant">
            <div class="bubble typing">{{ stage }}<span>...</span></div>
          </article>
        </div>

        <form @submit.prevent="send">
          <textarea
            v-model="draft"
            class="input-control"
            rows="3"
            maxlength="4000"
            :placeholder="placeholder"
            @keydown.enter.exact.prevent="send"
          ></textarea>
          <div class="composer-foot">
            <span>Enter 发送 · Shift+Enter 换行</span
            ><button
              class="btn btn-primary"
              :disabled="loading || !draft.trim()"
            >
              发送
            </button>
          </div>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import AppHeader from '../components/common/AppHeader.vue'
import { agentApi } from '../api/services'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const mode = ref('auto'),
  draft = ref(''),
  loading = ref(false),
  messages = ref([]),
  messagePanel = ref(null),
  stage = ref('正在路由')
const createSessionId = () =>
  `chat-${userStore.getUserId || 'user'}-${Date.now()}`
const sessionId = ref(createSessionId())
const modes = [
  { key: 'auto', label: '自动', description: '根据问题选择能力' },
  { key: 'chat', label: '普通聊天', description: '自由交流与解释' },
  { key: 'rag', label: '知识库 RAG', description: '从博客内容中检索' },
  { key: 'analytics', label: '运营 Agent', description: '安全分析运营数据' },
]
const isAdmin = computed(() => String(userStore.role).toUpperCase() === 'ADMIN')
const availableModes = computed(() =>
  modes.filter((x) => x.key !== 'analytics' || isAdmin.value)
)
const prompts = computed(() =>
  isAdmin.value
    ? [
        '介绍一下这个博客系统',
        '博客中有哪些技术文章？',
        '最近点赞最高的文章有哪些？',
      ]
    : ['介绍一下这个博客系统', '博客中有哪些技术文章？', '帮我解释 RAG 是什么']
)
const placeholder = computed(
  () =>
    ({
      auto: '输入问题，系统会自动选择能力…',
      chat: '和助手聊点什么…',
      rag: '询问博客知识库中的内容…',
      analytics: '询问用户、文章、点赞等运营指标…',
    })[mode.value]
)
function modeLabel(value) {
  return modes.find((x) => x.key === value)?.label || 'AI 助手'
}
function score(value) {
  return Number.isFinite(Number(value))
    ? `相关度 ${Number(value).toFixed(2)}`
    : ''
}
async function scrollBottom() {
  await nextTick()
  if (messagePanel.value)
    messagePanel.value.scrollTop = messagePanel.value.scrollHeight
}
function newSession() {
  if (
    messages.value.length &&
    !confirm('新建会话会清空当前页面消息，确定继续吗？')
  )
    return
  sessionId.value = createSessionId()
  messages.value = []
  draft.value = ''
}
async function send() {
  const content = draft.value.trim()
  if (!content || loading.value) return
  messages.value.push({ id: crypto.randomUUID(), role: 'user', content })
  draft.value = ''
  loading.value = true
  stage.value = '正在路由'
  await scrollBottom()
  const assistant = {
    id: crypto.randomUUID(),
    role: 'assistant',
    mode: mode.value,
    content: '',
    citations: [],
    suggestions: [],
  }
  messages.value.push(assistant)
  try {
    await userStore.ensureAgentToken()
    await agentApi.streamChat(
      { message: content, mode: mode.value, sessionId: sessionId.value },
      (event, data) => {
        if (event === 'tool.status') stage.value = data.message || '正在处理'
        else if (event === 'message.delta')
          assistant.content += data.content || ''
        else if (event === 'citation')
          assistant.citations = data.citations || []
        else if (event === 'chart') assistant.chart = data.chart
        else if (event === 'warning') assistant.warning = data.message
        else if (event === 'message.completed')
          Object.assign(assistant, data, {
            content: data.answer || assistant.content,
          })
        scrollBottom()
      }
    )
    if (!assistant.content) assistant.content = '没有返回内容'
  } catch (e) {
    assistant.mode = 'chat'
    assistant.content = e.message || 'Agent 调用失败'
    assistant.warning = '本次请求未完成'
  } finally {
    loading.value = false
    await scrollBottom()
  }
}
</script>

<style scoped>
.agent-wrap {
  padding-top: 34px;
}
.page {
  min-height: 100vh;
  padding-bottom: 3rem;
}
.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  border-radius: 1.25rem;
  padding: 1.8rem;
}
.hero p,
.hero h1 {
  margin: 0;
}
.hero p {
  color: #58e2c3;
  font-weight: 950;
}
.hero h1 {
  margin: 0.3rem 0;
  font-size: 2.2rem;
}
.hero span {
  color: #87a199;
}
.session-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.session {
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.045);
  padding: 0.5rem 0.8rem;
  font-size: 0.8rem;
}
.mode-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.6rem;
  margin: 1rem 0;
  border-radius: 1.15rem;
  padding: 0.7rem;
}
.mode-bar button {
  display: grid;
  gap: 0.2rem;
  border: 1px solid transparent;
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.035);
  color: #b4c8c2;
  padding: 0.75rem;
  text-align: left;
}
.mode-bar button.active {
  border-color: rgba(39, 216, 180, 0.55);
  background: rgba(39, 216, 180, 0.11);
  color: #68e8ca;
  box-shadow: inset 0 0 30px rgba(39, 216, 180, 0.05);
}
.mode-bar small {
  color: #718b84;
}
.chat {
  border-radius: 1.2rem;
  overflow: hidden;
}
.messages {
  height: 55vh;
  min-height: 28rem;
  overflow: auto;
  padding: 1.2rem;
}
.welcome {
  display: grid;
  place-items: center;
  gap: 0.8rem;
  min-height: 100%;
  color: #7f9992;
  text-align: center;
}
.welcome strong {
  color: #eef8f5;
  font-size: 1.5rem;
}
.welcome div,
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}
.welcome button,
.suggestions button {
  border: 1px solid var(--border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  padding: 0.5rem 0.8rem;
  color: #a7bdb7;
}
.message {
  display: flex;
  margin: 0.8rem 0;
}
.message.user {
  justify-content: flex-end;
}
.bubble {
  max-width: min(48rem, 88%);
  border: 1px solid var(--border);
  border-radius: 1rem 1rem 1rem 0.25rem;
  background: rgba(255, 255, 255, 0.055);
  padding: 1rem 1.1rem;
}
.user .bubble {
  border-color: rgba(39, 216, 180, 0.25);
  border-radius: 1rem 1rem 0.25rem 1rem;
  background: linear-gradient(135deg, #15967d, #0f6658);
  color: #f2fffc;
}
.meta {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  font-size: 0.8rem;
}
.meta span {
  opacity: 0.65;
}
.bubble p {
  white-space: pre-wrap;
  line-height: 1.7;
}
.warning {
  border-radius: 0.4rem;
  background: rgba(146, 64, 14, 0.2);
  color: #fdba74;
  padding: 0.65rem;
}
.citations,
.analysis {
  display: grid;
  gap: 0.45rem;
  margin-top: 0.8rem;
  border-top: 1px solid var(--border);
  padding-top: 0.8rem;
}
.citations a {
  color: #5be2c4;
  font-weight: 800;
}
.citations small {
  color: #7f9992;
}
.analysis pre {
  max-height: 18rem;
  overflow: auto;
  border-radius: 0.5rem;
  background: #0f172a;
  color: #d1fae5;
  padding: 0.8rem;
  white-space: pre-wrap;
}
.suggestions {
  justify-content: flex-start;
  margin-top: 0.8rem;
}
.typing {
  color: #79928b;
}
form {
  border-top: 1px solid var(--border);
  padding: 1rem;
}
textarea {
  resize: none;
}
.composer-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.7rem;
  color: #6f8982;
  font-size: 0.8rem;
}
@media (max-width: 780px) {
  .mode-bar {
    grid-template-columns: repeat(2, 1fr);
  }
  .hero {
    align-items: flex-start;
    flex-direction: column;
  }
}
@media (max-width: 480px) {
  .mode-bar {
    grid-template-columns: 1fr;
  }
  .composer-foot span {
    display: none;
  }
}
</style>
