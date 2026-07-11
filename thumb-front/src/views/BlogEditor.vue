<template>
  <main class="page-shell">
    <AppHeader />
    <div class="container-custom editor-wrap">
      <div class="page-head">
        <div>
          <span>{{ isEdit ? 'EDIT ARTICLE' : 'CREATE ARTICLE' }}</span>
          <h1>{{ isEdit ? '编辑博客' : '写一篇新博客' }}</h1>
          <p>专注内容本身，草稿会自动保存在当前浏览器。</p>
        </div>
        <router-link class="btn btn-outline" to="/me">返回个人中心</router-link>
      </div>
      <ErrorAlert :message="error" />
      <div class="editor-grid">
        <form class="section-card editor" @submit.prevent="submit">
          <label class="form-field"
            >文章标题<input
              v-model.trim="form.title"
              class="input-control title-input"
              maxlength="512"
              required
              placeholder="输入一个清晰、具体的标题"
            /><small>{{ form.title.length }} / 512</small></label
          ><label class="form-field"
            >内容格式<select v-model="form.contentFormat" class="input-control">
              <option value="PLAIN">纯文本</option>
              <option value="MARKDOWN">Markdown</option></select
            ><small>Markdown 原文在展示时会执行安全清洗</small></label
          ><label class="form-field"
            >封面图片地址<input
              v-model.trim="form.coverImg"
              class="input-control"
              type="url"
              placeholder="https://example.com/cover.jpg" /></label
          ><label class="form-field"
            >正文<textarea
              v-model="form.content"
              class="input-control content-input"
              required
              placeholder="从第一段开始写作……"
            ></textarea
            ><small>{{ form.content.length }} 字</small></label
          >
          <div v-if="success" class="form-success">{{ success }}</div>
          <footer>
            <span>{{ draftSaved ? '草稿已保存' : '正在保存草稿…' }}</span
            ><button class="btn btn-primary" :disabled="saving">
              {{ saving ? '正在保存…' : isEdit ? '保存修改' : '发布文章' }}
            </button>
          </footer>
        </form>
        <aside class="preview section-card">
          <div class="preview-head">封面预览</div>
          <div v-if="form.coverImg && !previewFailed" class="preview-image">
            <img
              :src="form.coverImg"
              alt="封面预览"
              @error="previewFailed = true"
            />
          </div>
          <div v-else class="placeholder">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M4 5h16v14H4V5Zm3 10 3-3 2.5 2.5L15 12l2 3H7Z"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linejoin="round"
              /></svg
            ><span>填写图片地址后显示预览</span>
          </div>
          <div class="preview-copy">
            <small>文章预览</small
            ><strong>{{ form.title || '文章标题' }}</strong>
            <div
              v-if="form.contentFormat === 'MARKDOWN'"
              class="markdown-preview"
              v-html="renderedMarkdown"
            ></div>
            <p v-else>{{ form.content.slice(0, 150) || '正文摘要会显示在这里。' }}</p>
          </div>
        </aside>
      </div>
    </div>
  </main>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import AppHeader from '../components/common/AppHeader.vue'
import ErrorAlert from '../components/common/ErrorAlert.vue'
import { blogApi } from '../api/services'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
const route = useRoute(),
  router = useRouter()
const isEdit = computed(() => Boolean(route.params.id))
const draftKey = computed(
  () => `blog-draft:${isEdit.value ? route.params.id : 'new'}`
)
const form = reactive({
  title: '',
  coverImg: '',
  content: '',
  contentFormat: 'MARKDOWN',
})
const initial = ref(''),
  saving = ref(false),
  draftSaved = ref(true),
  error = ref(''),
  success = ref(''),
  previewFailed = ref(false)
let timer
const renderedMarkdown = computed(() =>
  DOMPurify.sanitize(marked.parse(form.content || ''))
)
const snapshot = () => JSON.stringify(form)
const dirty = computed(() => snapshot() !== initial.value)
function saveDraft() {
  localStorage.setItem(draftKey.value, snapshot())
  draftSaved.value = true
}
function beforeUnload(e) {
  if (dirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
watch(
  form,
  () => {
    draftSaved.value = false
    previewFailed.value = false
    clearTimeout(timer)
    timer = setTimeout(saveDraft, 500)
  },
  { deep: true }
)
onBeforeRouteLeave(
  () => !dirty.value || confirm('还有未提交的修改，确定离开吗？')
)
onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload)
  try {
    if (isEdit.value) {
      const r = await blogApi.getDetail(route.params.id)
      Object.assign(form, r.data?.data || {})
    } else {
      const draft = localStorage.getItem(draftKey.value)
      if (draft) Object.assign(form, JSON.parse(draft))
    }
    initial.value = snapshot()
  } catch (e) {
    error.value = e.response?.data?.message || '文章加载失败'
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnload)
  clearTimeout(timer)
})
async function submit() {
  saving.value = true
  error.value = ''
  try {
    const payload = {
      title: form.title,
      coverImg: form.coverImg || null,
      content: form.content,
      contentFormat: form.contentFormat,
    }
    const r = isEdit.value
      ? await blogApi.update(route.params.id, payload)
      : await blogApi.create(payload)
    if (r.data?.code !== 0) throw new Error(r.data?.message || '保存失败')
    initial.value = snapshot()
    localStorage.removeItem(draftKey.value)
    success.value = isEdit.value ? '修改已保存' : '文章发布成功'
    setTimeout(
      () => router.push(isEdit.value ? `/blog/${route.params.id}` : '/me'),
      650
    )
  } catch (e) {
    error.value =
      e.response?.data?.message || e.message || '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}
</script>
<style scoped>
.editor-wrap {
  padding-top: 34px;
}
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
}
.page-head span {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.1em;
}
.page-head h1 {
  margin: 5px 0;
  font-size: 32px;
}
.page-head p {
  margin: 0;
  color: #64748b;
}
.editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.65fr);
  gap: 18px;
  margin-top: 16px;
}
.editor {
  display: grid;
  gap: 20px;
  padding: 24px;
}
.form-field small {
  justify-self: end;
  color: #94a3b8;
  font-size: 11px;
}
.title-input {
  font-size: 18px;
  font-weight: 750;
}
.content-input {
  min-height: 420px;
  resize: vertical;
  line-height: 1.8;
}
.editor footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #f1f5f9;
  padding-top: 18px;
}
.editor footer span {
  color: #94a3b8;
  font-size: 11px;
}
.preview {
  position: sticky;
  top: 90px;
  align-self: start;
  overflow: hidden;
}
.preview-head {
  border-bottom: 1px solid #e2e8f0;
  padding: 14px 16px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}
.preview-image,
.placeholder {
  aspect-ratio: 16/9;
  background: #f1f5f9;
}
.preview-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.placeholder {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 11px;
}
.placeholder svg {
  width: 34px;
}
.preview-copy {
  display: grid;
  gap: 8px;
  padding: 18px;
}
.preview-copy small {
  color: #0f766e;
  font-weight: 850;
}
.preview-copy strong {
  font-size: 19px;
}
.preview-copy p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.65;
}
@media (max-width: 850px) {
  .editor-grid {
    grid-template-columns: 1fr;
  }
  .preview {
    position: static;
  }
  .page-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
