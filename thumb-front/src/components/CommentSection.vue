<template>
  <section class="comments surface">
    <div class="head">
      <div>
        <h2>评论</h2>
        <span>{{ comments.length }} 条讨论</span>
      </div>
      <button class="btn btn-outline" @click="load">刷新</button>
    </div>
    <form v-if="userStore.isLoggedIn" @submit.prevent="submit">
      <textarea
        v-model.trim="content"
        class="input-control"
        maxlength="1000"
        required
        placeholder="写下你的评论…"
      ></textarea>
      <button class="btn btn-primary" :disabled="submitting">
        {{ submitting ? '发布中…' : '发表评论' }}
      </button>
    </form>
    <div v-else class="login-tip">
      登录后参与讨论。<router-link to="/login">去登录</router-link>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loading" class="empty">评论加载中…</div>
    <div v-else-if="!comments.length" class="empty">暂无评论，来坐沙发吧。</div>
    <article v-for="item in comments" :key="item.id" class="comment">
      <div class="avatar">
        {{
          String(item.username || 'U')
            .slice(0, 1)
            .toUpperCase()
        }}
      </div>
      <div class="body">
        <div class="meta">
          <strong>{{ item.username || `用户 ${item.userId}` }}</strong
          ><span>{{ formatDate(item.createdAt) }}</span>
        </div>
        <p>{{ item.content }}</p>
        <button
          v-if="userStore.isLoggedIn"
          class="reply-button"
          @click="replyingTo = replyingTo === item.id ? null : item.id"
        >
          回复
        </button>
        <button
          v-if="String(item.userId) === String(userStore.getUserId)"
          class="delete"
          @click="remove(item.id)"
        >
          删除
        </button>
        <form
          v-if="replyingTo === item.id"
          class="reply-form"
          @submit.prevent="submitReply(item.id)"
        >
          <input
            v-model.trim="replyContent"
            class="input-control"
            maxlength="1000"
            required
            :placeholder="`回复 ${item.username || '该用户'}`"
          />
          <button class="btn btn-primary" :disabled="submitting">
            发送回复
          </button>
        </form>
        <div v-for="child in item.children || []" :key="child.id" class="reply">
          <strong>{{ child.username || `用户 ${child.userId}` }}</strong
          ><span>{{ child.content }}</span>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { commentApi } from '../api/services'
import { useUserStore } from '../stores/user'
import { formatDate } from '../utils'
const props = defineProps({
  blogId: { type: [String, Number], required: true },
})
const userStore = useUserStore(),
  comments = ref([]),
  content = ref(''),
  replyContent = ref(''),
  replyingTo = ref(null),
  loading = ref(false),
  submitting = ref(false),
  error = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await commentApi.listByBlog(props.blogId)
    comments.value = Array.isArray(r.data?.data) ? r.data.data : []
  } catch (e) {
    error.value = e.response?.data?.message || '评论加载失败'
  } finally {
    loading.value = false
  }
}
async function submit() {
  submitting.value = true
  try {
    const r = await commentApi.create({
      blogId: String(props.blogId),
      content: content.value,
    })
    if (r.data?.code !== 0) throw new Error(r.data?.message)
    content.value = ''
    await load()
  } catch (e) {
    error.value = e.response?.data?.message || e.message || '评论发布失败'
  } finally {
    submitting.value = false
  }
}
async function submitReply(commentId) {
  submitting.value = true
  error.value = ''
  try {
    const r = await commentApi.reply(commentId, replyContent.value)
    if (r.data?.code !== 0) throw new Error(r.data?.message)
    replyContent.value = ''
    replyingTo.value = null
    await load()
  } catch (e) {
    error.value = e.response?.data?.message || e.message || '回复发布失败'
  } finally {
    submitting.value = false
  }
}
async function remove(id) {
  if (!confirm('确定删除这条评论吗？')) return
  try {
    await commentApi.remove(id)
    await load()
  } catch (e) {
    error.value = e.response?.data?.message || '删除失败'
  }
}
onMounted(load)
watch(() => props.blogId, load)
</script>

<style scoped>
.comments {
  max-width: 52rem;
  margin: 1.5rem auto 0;
  border-radius: 0.65rem;
  padding: 1.25rem;
}
.head,
.head > div,
.meta {
  display: flex;
  align-items: center;
}
.head {
  justify-content: space-between;
}
.head > div {
  gap: 0.7rem;
}
.head h2 {
  margin: 0;
}
.head span,
.meta span {
  color: #64748b;
  font-size: 0.85rem;
}
form {
  display: grid;
  gap: 0.7rem;
  margin: 1rem 0;
}
textarea {
  min-height: 6rem;
  resize: vertical;
}
form .btn {
  justify-self: end;
}
.comment {
  display: flex;
  gap: 0.8rem;
  border-top: 1px solid #e2e8f0;
  padding: 1rem 0;
}
.avatar {
  display: grid;
  place-items: center;
  flex: 0 0 2.3rem;
  height: 2.3rem;
  border-radius: 50%;
  background: #ccfbf1;
  color: #0f766e;
  font-weight: 900;
}
.body {
  flex: 1;
}
.meta {
  justify-content: space-between;
}
.body p {
  color: #334155;
  line-height: 1.7;
}
.delete,
.reply-button {
  border: 0;
  background: none;
  padding: 0;
}
.delete {
  color: #dc2626;
}
.reply-button {
  margin-right: 0.8rem;
  color: #0f766e;
}
.reply-form {
  grid-template-columns: 1fr auto;
  margin: 0.7rem 0;
}
.reply-form .btn {
  justify-self: auto;
}
.reply {
  display: grid;
  gap: 0.25rem;
  margin-top: 0.7rem;
  border-left: 3px solid #99f6e4;
  background: #f8fafc;
  padding: 0.7rem;
}
.empty,
.login-tip,
.error {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 0.5rem;
  background: #f8fafc;
  text-align: center;
}
.login-tip a {
  color: #0f766e;
  font-weight: 900;
}
.error {
  background: #fef2f2;
  color: #b91c1c;
}
</style>
