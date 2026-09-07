<template>
  <main class="page"><AppHeader />
    <div class="container-custom wrap">
      <section class="surface hero">
        <div><p>OPERATIONS INTELLIGENCE</p><h1>运营助手</h1><span>用自然语言问运营数据：Agent 会先思考、再执行 SQL、最后给出结论与建议。只读分析，不执行线上变更。</span></div>
        <b>只读分析 · 人工决策</b>
      </section>
      <nav class="tabs">
        <button :class="['tab', { active: tab === 'assistant' }]" @click="switchTab('assistant')">运营助手</button>
        <button :class="['tab', { active: tab === 'diagnose' }]" @click="switchTab('diagnose')">异常诊断</button>
        <button :class="['tab', { active: tab === 'logs' }]" @click="switchTab('logs')">历史日志</button>
      </nav>

      <!-- 运营助手 -->
      <template v-if="tab === 'assistant'">
        <section class="surface form assistant-form">
          <textarea v-model="assistantQuestion" class="input-control question-input" rows="2"
            placeholder="例如：按点赞数统计热门博客，返回前 10 篇；或：看一下运营情况"
            @keydown.enter.exact.prevent="askAssistant()"></textarea>
          <button class="btn btn-primary" :disabled="assistantRunning || !assistantQuestion.trim()" @click="askAssistant()">
            {{ assistantRunning ? 'Agent 思考中…' : '提问' }}
          </button>
        </section>
        <section v-if="assistantError" class="surface notice error"><strong>请求失败</strong>{{ assistantError }}</section>

        <section v-if="assistantEvents.length || assistantResult || assistantClarification" class="surface assistant">
          <div v-for="(item, index) in assistantEvents" :key="index" class="event">
            <span v-if="item.kind === 'status'" class="badge status-badge">思考</span>
            <span v-else-if="item.kind === 'plan'" class="badge plan-badge">计划</span>
            <span v-else-if="item.kind === 'memory'" class="badge memory-badge">记忆</span>
            <span v-else class="badge sql-badge">SQL</span>
            <div class="event-body">
              <template v-if="item.kind === 'memory'">
                <p class="event-line">{{ item.text }}</p>
              </template>
              <template v-else-if="item.kind === 'sql'">
                <p class="event-line">执行查询（返回 {{ number(item.rows) }} 行）</p>
                <pre class="sql-text">{{ item.text }}</pre>
              </template>
              <p v-else class="event-line">{{ item.text }}</p>
            </div>
          </div>

          <section v-if="assistantClarification" class="surface notice warn">
            <strong>需要确认方向</strong>{{ assistantClarification.message || assistantClarification.insight }}
            <div v-if="assistantClarification.options && assistantClarification.options.length" class="chips">
              <button v-for="option in assistantClarification.options" :key="option.value" class="chip"
                :disabled="assistantRunning" @click="askAssistant(option.value)">{{ option.label }}</button>
            </div>
          </section>

          <template v-if="assistantResult">
            <section class="surface result">
              <header class="result-head"><div><em>CONCLUSION</em><h3>结论</h3></div>
                <b :class="['status', String(assistantResult.status || '').toLowerCase()]">{{ assistantResult.status }}</b></header>
              <p class="summary">{{ (assistantResult.report || {}).summary || assistantResult.insight }}</p>

              <template v-if="assistantResult.chart && assistantResult.chart.data && assistantResult.chart.data.length">
                <h4>依据</h4>
                <div class="chart">
                  <div v-for="(row, index) in assistantResult.chart.data.slice(0, 8)" :key="index" class="bar-row">
                    <span class="bar-label">{{ printable(row[assistantResult.chart.xField]) }}</span>
                    <span class="bar-track"><span class="bar-fill" :style="{ width: barWidth(row[assistantResult.chart.yField], assistantResult.chart.data, assistantResult.chart.yField) }"></span></span>
                    <span class="bar-value">{{ number(row[assistantResult.chart.yField]) }}</span>
                  </div>
                </div>
              </template>
              <table v-else-if="assistantResult.data && assistantResult.data.length" class="table">
                <thead><tr><th v-for="(col, ci) in Object.keys(assistantResult.data[0]).slice(0, 6)" :key="ci">{{ col }}</th></tr></thead>
                <tbody>
                  <tr v-for="(row, ri) in assistantResult.data.slice(0, 8)" :key="ri">
                    <td v-for="(col, ci) in Object.keys(assistantResult.data[0]).slice(0, 6)" :key="ci">{{ printable(row[col]) }}</td>
                  </tr>
                </tbody>
              </table>

              <template v-if="assistantResult.suggestions && assistantResult.suggestions.length">
                <h4>建议</h4>
                <ul class="suggestions"><li v-for="(s, i) in assistantResult.suggestions" :key="i"><b>{{ s.action }}</b> · {{ s.reason }} <small>[{{ s.priority }}]</small></li></ul>
              </template>

              <details class="sql-detail"><summary>查看执行细节（意图 / 节点 / SQL / 安全检查）</summary>
                <dl class="detail-grid">
                  <dt>意图</dt><dd>{{ assistantResult.intent }}（{{ assistantResult.intentConfidence }}）</dd>
                  <dt>SQL 来源</dt><dd>{{ assistantResult.sqlSource || '—' }}</dd>
                  <dt>执行节点</dt><dd>{{ executionSteps(assistantResult).join(' → ') }}</dd>
                  <dt v-if="assistantResult.sql">SQL</dt><dd v-if="assistantResult.sql"><pre class="sql-text">{{ assistantResult.sql }}</pre></dd>
                  <dt>返回行数</dt><dd>{{ (assistantResult.data || []).length }}</dd>
                </dl>
              </details>
            </section>
          </template>
        </section>
      </template>

      <!-- 异常诊断 -->
      <template v-else-if="tab === 'diagnose'">
        <section class="surface form">
          <label>分析场景<select v-model="query.scenario" class="input-control"><option v-for="item in scenarios" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label>观察开始<input v-model="query.observedFrom" class="input-control" type="date" :max="query.observedTo" /></label>
          <label>观察结束<input v-model="query.observedTo" class="input-control" type="date" :min="query.observedFrom" :max="today" /></label>
          <label>标签（可选）<input v-model.trim="query.tag" class="input-control" placeholder="例如：Java" /></label>
          <button class="btn btn-primary" :disabled="loading || invalidWindow" @click="analyze">{{ loading ? '正在核验…' : '开始诊断' }}</button>
        </section>
        <p v-if="invalidWindow" class="error">请选择 1 至 30 天的观察窗口，且开始时间不能晚于结束时间。</p>
        <section v-if="error" class="surface notice error"><strong>分析未完成</strong>{{ error }}</section>
        <section v-else-if="loading" class="surface notice"><strong>正在生成带证据的运营发现…</strong>分析仅查询数据，不创建或执行运营动作。</section>
        <section v-else-if="clarification" class="surface notice warn"><strong>需要补充信息</strong>{{ clarification.message || '请补全时间窗口或目标。' }}<div v-if="clarification.options?.length" class="chips"><span v-for="item in clarification.options" :key="String(item)">{{ printable(item) }}</span></div></section>
        <section v-else-if="analyzed && !findings.length" class="surface notice"><strong>未发现可确认信号</strong>当前窗口没有满足最小样本量和基线要求的运营发现。</section>
        <section v-if="findings.length"><h2>已验证的运营发现 <small>{{ findings.length }} 项</small></h2>
          <article v-for="item in findings" :key="item.findingId || item.id || item.type" class="surface finding">
            <header><div><em>{{ typeLabel(item.type) }}</em><h3>{{ item.metric?.displayName || item.metric?.key || item.type }}</h3></div><b :class="['status', String(item.status || 'OPEN').toLowerCase()]">{{ statusLabel(item.status) }}</b></header>
            <p class="scope">{{ targetLabel(item.target) }} · {{ timeLabel(item.observation) }}</p>
            <div class="metrics"><div><small>当前值</small><strong>{{ number(item.evidence?.currentValue ?? item.currentValue) }}</strong></div><div><small>基线均值</small><strong>{{ number(item.evidence?.baselineMean ?? item.baselineValue) }}</strong></div><div><small>异常分数</small><strong>{{ number(item.evidence?.anomalyScore ?? item.anomalyScore) }}</strong></div><div><small>样本量（当前/基线）</small><strong>{{ sampleSize(item) }}</strong></div><div><small>置信度</small><strong>{{ percent(item.confidence) }}</strong></div></div>
            <div class="details"><div><h4>证据</h4><dl><dt>指标版本</dt><dd>{{ item.metric?.version || item.metricVersion || '未提供' }}</dd><dt>最小样本量</dt><dd>{{ number(item.evidence?.minimumSampleSize) }}</dd><dt>数据新鲜度</dt><dd>{{ date(item.observation?.freshAt || item.dataFreshAt) }}</dd><dt>分析记录</dt><dd>{{ item.analysisLogId || '未提供' }}</dd></dl></div><div><h4>限制条件</h4><ul v-if="limits(item).length"><li v-for="limit in limits(item)" :key="printable(limit)">{{ printable(limit) }}</li></ul><p v-else>未返回额外限制条件。</p></div></div>
          </article>
        </section>
      </template>

      <!-- 历史日志 -->
      <template v-else>
        <section class="surface form logs-form">
          <label>共 {{ logsTotal }} 条分析记录</label>
          <button class="btn btn-primary" :disabled="logsLoading" @click="reloadLogs">{{ logsLoading ? '加载中…' : '刷新' }}</button>
        </section>
        <section v-if="logsError" class="surface notice error"><strong>加载失败</strong>{{ logsError }}</section>
        <section v-else class="surface">
          <table class="table">
            <thead><tr><th>时间</th><th>问题</th><th>意图</th><th>状态</th><th>行数</th><th></th></tr></thead>
            <tbody>
              <tr v-for="item in logs" :key="item.id">
                <td>{{ date(item.created_at) }}</td>
                <td class="log-question">{{ item.question }}</td>
                <td>{{ item.intent }}</td>
                <td><b :class="['status', String(item.status || '').toLowerCase()]">{{ item.status }}</b></td>
                <td>{{ number(item.row_count) }}</td>
                <td><details><summary>详情</summary><pre class="sql-text">{{ logDetail(item) }}</pre></details></td>
              </tr>
              <tr v-if="!logs.length"><td colspan="6" class="empty">暂无分析记录</td></tr>
            </tbody>
          </table>
          <div class="pager" v-if="logsTotal > logsSize">
            <button class="btn btn-ghost" :disabled="logsPage <= 1" @click="changeLogsPage(logsPage - 1)">上一页</button>
            <span>{{ logsPage }} / {{ Math.max(1, Math.ceil(logsTotal / logsSize)) }}</span>
            <button class="btn btn-ghost" :disabled="logsPage * logsSize >= logsTotal" @click="changeLogsPage(logsPage + 1)">下一页</button>
          </div>
        </section>
      </template>
    </div>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import AppHeader from '../components/common/AppHeader.vue'
import { agentApi } from '../api/services'
import { useUserStore } from '../stores/user'

const today = new Date().toISOString().slice(0, 10)
const beforeDays = (days) => new Date(Date.now() - days * 86400000).toISOString().slice(0, 10)

// 运营助手
const tab = ref('assistant')
const assistantQuestion = ref('')
const assistantRunning = ref(false)
const assistantError = ref('')
const assistantEvents = ref([])
const assistantResult = ref(null)
const assistantClarification = ref(null)

function assistantSessionId() {
  const userId = useUserStore().getUserId
  const key = `ops-assistant-${userId ?? 'anon'}`
  let sessionId = localStorage.getItem(key)
  if (!sessionId) {
    sessionId = `${key}-${Date.now().toString(36)}`
    localStorage.setItem(key, sessionId)
  }
  return sessionId
}

async function askAssistant(forcedIntent) {
  if (assistantRunning.value || !assistantQuestion.value.trim()) return
  assistantRunning.value = true
  assistantError.value = ''
  assistantResult.value = null
  assistantClarification.value = null
  assistantEvents.value = []
  try {
    await useUserStore().ensureAgentToken()
    await agentApi.streamAnalytics(
      { question: assistantQuestion.value.trim(), sessionId: assistantSessionId(), ...(forcedIntent ? { forcedIntent } : {}) },
      (event, payload) => {
        if (event === 'status') assistantEvents.value.push({ kind: 'status', text: payload.message || payload.stage })
        else if (event === 'plan') assistantEvents.value.push({ kind: 'plan', text: payload.declaration })
        else if (event === 'sql') assistantEvents.value.push({ kind: 'sql', text: payload.sql, rows: payload.rowCount })
        else if (event === 'memory') assistantEvents.value.push({ kind: 'memory', text: memoryText(payload) })
        else if (event === 'clarification') assistantClarification.value = payload
        else if (event === 'result') assistantResult.value = payload
      }
    )
  } catch (cause) {
    assistantError.value = cause.response?.data?.detail || cause.response?.data?.message || cause.message || '运营助手请求失败'
  } finally {
    assistantRunning.value = false
  }
}

function memoryText(payload) {
  if (!payload || payload.enabled === false) return ''
  const parts = []
  if (payload.longTermEntries) parts.push(`长期记忆 ${payload.longTermEntries} 条`)
  if (payload.shortTurns) parts.push(`本会话已记住 ${payload.shortTurns} 轮`)
  if (payload.sessionMemoryEntries) parts.push(`会话结论 ${payload.sessionMemoryEntries} 条`)
  return parts.length ? `已载入记忆：${parts.join('，')}` : ''
}

// 异常诊断
const scenarios = [{ value: 'CONTENT_ENGAGEMENT_DROP', label: '内容互动下滑' }, { value: 'COMMENT_RISK_SPIKE', label: '评论风险激增' }, { value: 'CONTENT_SUPPLY_GAP', label: '内容供给缺口' }]
const query = ref({ scenario: scenarios[0].value, observedFrom: beforeDays(6), observedTo: today, tag: '' })
const loading = ref(false), error = ref(''), findings = ref([]), clarification = ref(null), analyzed = ref(false)
const selectedDays = computed(() => {
  if (!query.value.observedFrom || !query.value.observedTo) return 0
  return Math.floor((new Date(`${query.value.observedTo}T00:00:00`) - new Date(`${query.value.observedFrom}T00:00:00`)) / 86400000) + 1
})
const invalidWindow = computed(() => selectedDays.value < 1 || selectedDays.value > 30)
async function analyze() {
  if (loading.value || invalidWindow.value) return
  loading.value = true; error.value = ''; findings.value = []; clarification.value = null; analyzed.value = false
  try {
    await useUserStore().ensureAgentToken()
    const response = await agentApi.operationsAnalyze({ currentDays: selectedDays.value, baselineDays: 56, ...(query.value.tag ? { tag: query.value.tag } : {}) })
    const data = response.data?.data ?? response.data ?? {}
    const allFindings = Array.isArray(data.findings) ? data.findings : []
    findings.value = allFindings.filter((item) => item.type === query.value.scenario)
    clarification.value = data.needsClarification || (data.status === 'NEEDS_CLARIFICATION' ? data : null)
    analyzed.value = true
  } catch (cause) {
    error.value = cause.response?.data?.detail || cause.response?.data?.message || cause.message || '无法连接运营分析服务，请稍后重试。'
  } finally {
    loading.value = false
  }
}

// 历史日志
const logs = ref([])
const logsTotal = ref(0)
const logsPage = ref(1)
const logsSize = 20
const logsLoading = ref(false)
const logsError = ref('')
async function reloadLogs() {
  logsLoading.value = true
  logsError.value = ''
  try {
    await useUserStore().ensureAgentToken()
    const response = await agentApi.analyticsLogsPage({ page: logsPage.value, size: logsSize })
    const body = response.data
    if (body.code !== 0) throw new Error(body.message || '加载日志失败')
    logs.value = (body.data && body.data.list) || []
    logsTotal.value = (body.data && body.data.total) || 0
  } catch (cause) {
    logsError.value = cause.response?.data?.detail || cause.response?.data?.message || cause.message || '无法加载日志'
  } finally {
    logsLoading.value = false
  }
}
function changeLogsPage(page) {
  logsPage.value = Math.max(1, page)
  reloadLogs()
}
const logDetail = (item) => [
  `SQL: ${item.sql_text || '—'}`,
  `结论: ${item.insight || '—'}`,
  item.error_message ? `错误: ${item.error_message}` : null,
].filter(Boolean).join('\n\n')

function switchTab(name) {
  tab.value = name
  if (name === 'logs' && !logs.value.length) reloadLogs()
}

const executionSteps = (result) => {
  const plan = result.executionPlan || result.plan || {}
  return (plan.steps || []).map((step) => step.name).filter(Boolean)
}
const barWidth = (value, rows, yField) => {
  const nums = (rows || []).map((row) => Number(row[yField]) || 0)
  const max = Math.max(...nums, 1)
  return `${Math.max(4, Math.round(((Number(value) || 0) / max) * 100))}%`
}
const number = (v) => v === null || v === undefined || v === '' ? '—' : Number.isFinite(Number(v)) ? Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 4 }) : String(v)
const sampleSize = (item) => {
  const current = item.evidence?.currentSampleSize
  const baseline = item.evidence?.baselineSampleSize
  return current === undefined && baseline === undefined ? number(item.sampleSize) : `${number(current)} / ${number(baseline)}`
}
const percent = (v) => v === null || v === undefined ? '—' : `${(Number(v) * 100).toFixed(0)}%`
const date = (v) => v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '未提供'
const printable = (v) => typeof v === 'string' ? v : JSON.stringify(v)
const limits = (item) => Array.isArray(item.limitations) ? item.limitations : Array.isArray(item.limitationsJson) ? item.limitationsJson : []
const targetLabel = (target) => target?.type ? `目标：${target.type}${target.id ? ` / ${target.id}` : ''}` : '目标：平台整体'
const timeLabel = (o) => o?.from && o?.to ? `${date(o.from)} 至 ${date(o.to)}` : '观察窗口未提供'
const typeLabel = (t) => ({ CONTENT_ENGAGEMENT_DROP: '内容互动', COMMENT_RISK_SPIKE: '评论风险', CONTENT_SUPPLY_GAP: '供给缺口' })[t] || t || '运营发现'
const statusLabel = (s) => ({ OPEN: '已确认', INSUFFICIENT_DATA: '数据不足', NEEDS_CLARIFICATION: '待澄清', SUCCESS: '成功', FAILED: '失败', DENIED: '拒绝' })[s] || s || '已确认'
</script>

<style scoped>
.page{min-height:100vh;padding-bottom:3rem}.wrap{padding-top:34px}.surface{border-radius:1.2rem}.hero{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:1.8rem}.hero p{margin:0;color:#58e2c3;font-size:.75rem;font-weight:900;letter-spacing:.12em}.hero h1{margin:.35rem 0}.hero span,.scope,.notice{color:#8ca49e}.hero>b,em,.status{border:1px solid var(--border);border-radius:999px;padding:.4rem .7rem;font-size:.8rem;font-style:normal}.form{display:grid;grid-template-columns:repeat(4,1fr) auto;gap:1rem;align-items:end;margin:1rem 0;padding:1.1rem}.form label{display:grid;gap:.4rem;color:#b5c9c3;font-size:.82rem;font-weight:800}.error{color:#fca5a5}.notice{display:grid;gap:.4rem;padding:1.3rem}.notice strong{color:#edf8f5}.notice.error{border:1px solid rgba(239,68,68,.45)}.notice.warn{border:1px solid rgba(245,158,11,.4)}.chips{display:flex;gap:.5rem;flex-wrap:wrap}.chips span,.chip{border-radius:999px;background:rgba(245,158,11,.1);padding:.35rem .6rem;color:#fcd34d}.chip{border:1px solid rgba(245,158,11,.4);cursor:pointer;font-weight:700}.chip:disabled{opacity:.5;cursor:default}h2{margin:1.5rem 0 .75rem}h2 small{color:#83a198;font-size:.8rem}.finding{margin-bottom:1rem;padding:1.3rem}.finding header{display:flex;justify-content:space-between;gap:1rem}.finding h3{margin:.55rem 0 0}.finding em{color:#63e2c5}.status.open,.status.success{color:#69ebcd}.status.insufficient_data,.status.needs_clarification{color:#fcd34d}.status.failed,.status.denied{color:#fca5a5}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:.65rem;margin:1rem 0}.metrics div{display:grid;gap:.25rem;border-radius:.75rem;background:rgba(255,255,255,.04);padding:.75rem}.metrics small,dt{color:#79928b}.details{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;border-top:1px solid var(--border);padding-top:1rem}.details h4{margin:0 0 .55rem}.details p,.details ul{margin:0;color:#95aaa4;line-height:1.6}.details ul{padding-left:1.1rem}dl{display:grid;grid-template-columns:7rem 1fr;gap:.35rem .7rem;margin:0;font-size:.86rem}dd{margin:0;color:#d5e5e0;word-break:break-word}
.tabs{display:flex;gap:.5rem;margin:1rem 0}.tab{background:none;border:1px solid var(--border);border-radius:999px;color:#8ca49e;padding:.45rem 1.1rem;font-weight:800;cursor:pointer}.tab.active{background:rgba(88,226,195,.12);border-color:#58e2c3;color:#58e2c3}
.assistant-form{grid-template-columns:1fr auto}.question-input{resize:vertical;font-family:inherit;min-height:3rem}.assistant{padding:1.3rem}.event{display:grid;grid-template-columns:3.5rem 1fr;gap:.8rem;padding:.55rem 0;border-bottom:1px solid var(--border)}.badge{justify-self:start;border-radius:999px;padding:.28rem .6rem;font-size:.72rem;font-weight:900}.status-badge{background:rgba(245,158,11,.12);color:#fcd34d}.plan-badge{background:rgba(88,226,195,.12);color:#58e2c3}.sql-badge{background:rgba(96,165,250,.12);color:#93c5fd}.event-body{min-width:0}.event-line{margin:0;color:#d5e5e0;line-height:1.7}.sql-text{background:rgba(0,0,0,.25);border-radius:.6rem;padding:.8rem;overflow:auto;font-size:.78rem;color:#a9c8bf;white-space:pre-wrap;word-break:break-all;margin:.4rem 0 0}
.result{margin-top:1rem;padding:1.3rem}.result-head{display:flex;justify-content:space-between;align-items:center;gap:1rem}.result-head em{color:#63e2c5;font-style:normal;font-size:.72rem;font-weight:900;letter-spacing:.12em}.result h3{margin:.35rem 0 0}.result h4{margin:1.2rem 0 .55rem;color:#b5c9c3}.summary{line-height:1.8;color:#d5e5e0;background:rgba(255,255,255,.04);border-radius:.75rem;padding:1rem}
.chart{display:grid;gap:.45rem;margin:.6rem 0}.bar-row{display:grid;grid-template-columns:9rem 1fr 4rem;gap:.6rem;align-items:center}.bar-label{color:#95aaa4;font-size:.8rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bar-track{background:rgba(255,255,255,.06);border-radius:999px;height:.6rem}.bar-fill{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#2fd6a8,#58e2c3)}.bar-value{color:#d5e5e0;font-size:.8rem;text-align:right}
.table{width:100%;border-collapse:collapse;font-size:.8rem;margin-top:.6rem}.table th,.table td{border:1px solid var(--border);padding:.4rem .55rem;text-align:left;color:#d5e5e0;vertical-align:top}.table th{color:#8ca49e;background:rgba(255,255,255,.03)}.table .empty{text-align:center;color:#79928b}.log-question{max-width:22rem}.pager{display:flex;align-items:center;gap:1rem;justify-content:flex-end;margin-top:.8rem;color:#8ca49e}.btn-ghost{background:none;border:1px solid var(--border);border-radius:.6rem;color:#d5e5e0;padding:.35rem .8rem;cursor:pointer}.detail-grid{grid-template-columns:6rem 1fr}.detail-grid dd pre{margin:0}
.suggestions{list-style:none;padding:0;margin:0;display:grid;gap:.5rem}.suggestions li{border:1px solid var(--border);border-radius:.75rem;padding:.7rem .9rem;color:#d5e5e0;line-height:1.6}.suggestions small{color:#fcd34d}.logs-form{grid-template-columns:1fr auto}
@media(max-width:900px){.form{grid-template-columns:repeat(2,1fr)}.metrics{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.hero,.finding header{align-items:flex-start;flex-direction:column}.form,.assistant-form,.metrics,.details{grid-template-columns:1fr}.form button{width:100%}.event{grid-template-columns:1fr}}
</style>
