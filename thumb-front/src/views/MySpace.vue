<template>
  <main class="page-shell">
    <AppHeader />
    <div class="container-custom workspace">
      <section class="profile section-card">
        <div class="avatar">{{ initial }}</div>
        <div class="identity">
          <span>个人工作台</span>
          <h1>{{ userStore.displayName }}</h1>
          <p>
            {{ userStore.currentUser?.email || '未设置邮箱' }} ·
            {{ userStore.role }}
          </p>
        </div>
        <button class="btn btn-outline" @click="editingProfile = !editingProfile">
          编辑资料
        </button>
        <router-link class="btn btn-primary" to="/blog/new"
          ><svg viewBox="0 0 24 24" fill="none">
            <path
              d="M12 5v14M5 12h14"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            /></svg
          >新建博客</router-link
        >
      </section>
      <form
        v-if="editingProfile"
        class="profile-form section-card"
        @submit.prevent="saveProfile"
      >
        <label class="form-field"
          >姓名<input
            v-model.trim="profile.fullName"
            class="input-control"
            maxlength="100"
        /></label>
        <label class="form-field"
          >邮箱<input
            v-model.trim="profile.email"
            class="input-control"
            type="email"
            maxlength="255"
            required
        /></label>
        <button class="btn btn-primary" :disabled="profileSaving">保存资料</button>
      </form>
      <section class="stats">
        <article class="section-card">
          <span>我的文章</span><strong>{{ blogs.length }}</strong>
        </article>
        <article class="section-card">
          <span>累计点赞</span><strong>{{ totalThumbs }}</strong>
        </article>
        <article class="section-card">
          <span>最近发布</span><strong class="date">{{ latestDate }}</strong>
        </article>
      </section>
      <section class="list-head">
        <div>
          <h2>我的文章</h2>
          <p>管理已经发布的内容与草稿。</p>
        </div>
      </section>
      <div class="toolbar section-card">
        <input
          v-model.trim="keyword"
          class="input-control"
          placeholder="搜索我的文章"
        /><select v-model="sortBy" class="input-control">
          <option value="latest">最新发布</option>
          <option value="hot">最多点赞</option>
          <option value="title">标题排序</option></select
        ><button class="btn btn-outline" :disabled="loading" @click="load">
          刷新
        </button>
      </div>
      <ErrorAlert :message="error" /><ApiLoader
        :loading="loading"
        message="正在加载你的文章…"
      /><EmptyState
        v-if="!loading && !pagedBlogs.length"
        :title="keyword ? '没有匹配的文章' : '还没有发布文章'"
        :description="
          keyword ? '试试其他关键词。' : '从一篇新博客开始记录与分享。'
        "
        ><router-link v-if="!keyword" class="btn btn-primary" to="/blog/new"
          >开始创作</router-link
        ></EmptyState
      >
      <div v-else class="blog-list">
        <article
          v-for="blog in pagedBlogs"
          :key="blog.id"
          class="item section-card"
        >
          <div class="item-main">
            <span>{{ formatDate(blog.createTime, 'YYYY-MM-DD') }}</span>
            <h3>{{ blog.title }}</h3>
            <p class="line-clamp-2">
              {{ blog.summary || truncateString(blog.content, 120) }}
            </p>
          </div>
          <div class="item-side">
            <span>{{ blog.thumbCount || 0 }} 个赞</span>
            <div>
              <router-link class="btn btn-outline" :to="`/blog/${blog.id}`"
                >查看</router-link
              ><router-link class="btn btn-soft" :to="`/blog/${blog.id}/edit`"
                >编辑</router-link
              ><button class="btn btn-danger" @click="remove(blog)">
                删除
              </button>
            </div>
          </div>
        </article>
      </div>
      <Pagination
        :page="page"
        :total-pages="totalPages"
        @change="page = $event"
      />
    </div>
  </main>
</template>
<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import AppHeader from '../components/common/AppHeader.vue'
import ApiLoader from '../components/common/ApiLoader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorAlert from '../components/common/ErrorAlert.vue'
import Pagination from '../components/common/Pagination.vue'
import { blogApi } from '../api/services'
import { useUserStore } from '../stores/user'
import { formatDate, truncateString } from '../utils'
const userStore = useUserStore(),
  blogs = ref([]),
  loading = ref(false),
  error = ref(''),
  keyword = ref(''),
  sortBy = ref('latest'),
  page = ref(1)
const editingProfile = ref(false)
const profileSaving = ref(false)
const profile = reactive({
  fullName: userStore.currentUser?.fullName || '',
  email: userStore.currentUser?.email || '',
})
const pageSize = 6
const initial = computed(() =>
  String(userStore.displayName || 'U')
    .slice(0, 1)
    .toUpperCase()
)
const totalThumbs = computed(() =>
  blogs.value.reduce((s, x) => s + (Number(x.thumbCount) || 0), 0)
)
const latestDate = computed(() =>
  blogs.value.length
    ? formatDate(
        [...blogs.value].sort(
          (a, b) => new Date(b.createTime) - new Date(a.createTime)
        )[0].createTime,
        'MM-DD'
      )
    : '—'
)
const filtered = computed(() => {
  const q = keyword.value.toLowerCase()
  const list = blogs.value.filter(
    (x) => !q || `${x.title} ${x.content}`.toLowerCase().includes(q)
  )
  return [...list].sort((a, b) =>
    sortBy.value === 'hot'
      ? (b.thumbCount || 0) - (a.thumbCount || 0)
      : sortBy.value === 'title'
        ? a.title.localeCompare(b.title, 'zh-CN')
        : new Date(b.createTime) - new Date(a.createTime)
  )
})
const totalPages = computed(() =>
  Math.max(1, Math.ceil(filtered.value.length / pageSize))
)
const pagedBlogs = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize)
)
watch([keyword, sortBy], () => (page.value = 1))
async function saveProfile() {
  profileSaving.value = true
  error.value = ''
  try {
    await userStore.updateProfile(profile)
    editingProfile.value = false
  } catch (e) {
    error.value = e.response?.data?.message || e.message || '资料保存失败'
  } finally {
    profileSaving.value = false
  }
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await blogApi.getMine()
    blogs.value = Array.isArray(r.data?.data) ? r.data.data : []
  } catch (e) {
    error.value = e.response?.data?.message || '文章加载失败'
  } finally {
    loading.value = false
  }
}
async function remove(blog) {
  if (!confirm(`删除后无法恢复，确定删除《${blog.title}》吗？`)) return
  try {
    await blogApi.remove(blog.id)
    blogs.value = blogs.value.filter((x) => x.id !== blog.id)
  } catch (e) {
    error.value = e.response?.data?.message || '删除失败'
  }
}
onMounted(load)
</script>
<style scoped>
.workspace {
  padding-top: 28px;
}
.profile {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 24px;
}
.avatar {
  display: grid;
  width: 64px;
  height: 64px;
  place-items: center;
  border-radius: 18px;
  background: #0f766e;
  color: white;
  font-size: 24px;
  font-weight: 950;
}
.identity {
  flex: 1;
}
.identity > span {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.1em;
}
.identity h1 {
  margin: 3px 0;
  font-size: 26px;
}
.identity p,
.list-head p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}
.profile svg {
  width: 17px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-top: 16px;
}
.profile-form {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  align-items: end;
  gap: 12px;
  margin-top: 14px;
  padding: 18px;
}
.stats article {
  display: grid;
  gap: 8px;
  padding: 20px;
}
.stats span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}
.stats strong {
  font-size: 28px;
}
.stats .date {
  font-size: 22px;
}
.list-head {
  margin: 34px 0 14px;
}
.list-head h2 {
  margin: 0 0 3px;
  font-size: 23px;
}
.toolbar {
  display: grid;
  grid-template-columns: 1fr 160px auto;
  gap: 10px;
  padding: 12px;
}
.blog-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}
.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 20px;
}
.item-main {
  min-width: 0;
  flex: 1;
}
.item-main > span,
.item-side > span {
  color: #94a3b8;
  font-size: 11px;
  font-weight: 750;
}
.item h3 {
  margin: 5px 0;
  font-size: 18px;
}
.item p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.65;
}
.item-side {
  display: grid;
  justify-items: end;
  gap: 12px;
}
.item-side div {
  display: flex;
  gap: 7px;
}
@media (max-width: 700px) {
  .profile {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .profile .btn {
    width: 100%;
  }
  .stats {
    grid-template-columns: 1fr;
  }
  .profile-form {
    grid-template-columns: 1fr;
  }
  .toolbar {
    grid-template-columns: 1fr;
  }
  .item {
    align-items: flex-start;
    flex-direction: column;
  }
  .item-side {
    width: 100%;
    justify-items: start;
  }
  .item-side div {
    flex-wrap: wrap;
  }
}
</style>
