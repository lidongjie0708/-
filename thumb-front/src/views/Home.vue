<template>
  <main class="page-shell">
    <AppHeader />
    <section class="hero">
      <div class="container-custom hero-inner">
        <div class="hero-copy">
          <span class="eyebrow">BLOGS × AI KNOWLEDGE</span>
          <h1>发现值得阅读的内容，<br />让知识持续流动。</h1>
          <p>浏览社区文章、参与讨论，也可以让 AI 助手从知识库中找到答案。</p>
          <div class="hero-actions">
            <a class="btn btn-primary" href="#articles">浏览文章</a
            ><router-link
              v-if="userStore.isLoggedIn"
              class="btn btn-outline"
              to="/agent"
              >使用 AI 助手</router-link
            ><router-link v-else class="btn btn-outline" to="/register"
              >加入社区</router-link
            >
          </div>
        </div>
        <div class="metrics section-card">
          <div>
            <strong>{{ blogs.length }}</strong
            ><span>公开文章</span>
          </div>
          <div>
            <strong>{{ formatNumber(blogStore.totalThumbs) }}</strong
            ><span>累计点赞</span>
          </div>
          <div>
            <strong>{{ likedCount }}</strong
            ><span>我的喜欢</span>
          </div>
        </div>
      </div>
    </section>
    <section id="articles" class="container-custom content">
      <div class="section-heading">
        <div>
          <span>DISCOVER</span>
          <h2>社区文章</h2>
          <p>从最新内容到热门讨论，找到你感兴趣的话题。</p>
        </div>
      </div>
      <div class="toolbar section-card">
        <label class="search"
          ><svg viewBox="0 0 24 24" fill="none">
            <circle
              cx="11"
              cy="11"
              r="6.5"
              stroke="currentColor"
              stroke-width="1.7"
            />
            <path
              d="m16 16 4 4"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
            /></svg
          ><input
            v-model="keyword"
            type="search"
            placeholder="搜索标题、摘要或正文" /></label
        ><select v-model="sortBy" class="input-control">
          <option value="latest">最新发布</option>
          <option value="hot">最多点赞</option>
          <option value="title">标题排序</option></select
        ><button
          class="btn btn-outline"
          :disabled="blogStore.loading"
          @click="refreshBlogs"
        >
          刷新
        </button>
      </div>
      <ErrorAlert :message="blogStore.error" /><ApiLoader
        :loading="blogStore.loading && !blogs.length"
        message="正在加载文章…"
      /><EmptyState
        v-if="!blogStore.loading && !filteredBlogs.length"
        :title="keyword ? '没有匹配的文章' : '暂无公开文章'"
        :description="
          keyword ? '换一个关键词再试试。' : '第一篇精彩内容正在路上。'
        "
      />
      <div v-else class="blog-grid">
        <BlogCard v-for="blog in filteredBlogs" :key="blog.id" :blog="blog" />
      </div>
    </section>
  </main>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import AppHeader from '../components/common/AppHeader.vue'
import ApiLoader from '../components/common/ApiLoader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorAlert from '../components/common/ErrorAlert.vue'
import BlogCard from '../components/BlogCard.vue'
import { useBlogStore } from '../stores/blog'
import { useThumbStore } from '../stores/thumb'
import { useUserStore } from '../stores/user'
import { formatNumber } from '../utils'
const blogStore = useBlogStore(),
  thumbStore = useThumbStore(),
  userStore = useUserStore()
const keyword = ref(''),
  sortBy = ref('latest')
const blogs = computed(() => blogStore.blogs)
const likedCount = computed(
  () =>
    blogs.value.filter((x) => x.hasThumb || thumbStore.hasThumb(x.id)).length
)
const filteredBlogs = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  const list = blogs.value.filter(
    (x) =>
      !q ||
      `${x.title || ''} ${x.summary || ''} ${x.content || ''}`
        .toLowerCase()
        .includes(q)
  )
  return [...list].sort((a, b) =>
    sortBy.value === 'hot'
      ? (Number(b.thumbCount) || 0) - (Number(a.thumbCount) || 0)
      : sortBy.value === 'title'
        ? String(a.title || '').localeCompare(String(b.title || ''), 'zh-CN')
        : new Date(b.createTime || 0) - new Date(a.createTime || 0)
  )
})
async function refreshBlogs() {
  await blogStore.fetchBlogs(true)
}
watch(blogs, (x) => thumbStore.setMultipleThumbStatus(x), { immediate: true })
onMounted(() => blogStore.fetchBlogs())
</script>
<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  border-bottom: 1px solid var(--border);
}
.hero::after {
  position: absolute;
  top: 50px;
  right: -110px;
  width: 480px;
  height: 480px;
  border: 1px solid rgba(67, 225, 190, 0.12);
  border-radius: 50%;
  box-shadow:
    0 0 0 70px rgba(39, 216, 180, 0.025),
    0 0 0 150px rgba(39, 216, 180, 0.018);
  content: '';
  pointer-events: none;
}
.hero-inner {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  align-items: center;
  gap: 60px;
  position: relative;
  z-index: 1;
  padding-top: 100px;
  padding-bottom: 96px;
}
.eyebrow,
.section-heading span {
  color: #5fe6c7;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
}
.hero h1 {
  margin: 14px 0 18px;
  max-width: 820px;
  font-size: clamp(44px, 6vw, 76px);
  line-height: 1.02;
  letter-spacing: -0.06em;
  background: linear-gradient(130deg, #f5fffc 25%, #a7c9c0 72%, #52d9bb);
  background-clip: text;
  color: transparent;
}
.hero-copy p {
  max-width: 620px;
  color: #90aaa3;
  font-size: 18px;
  line-height: 1.8;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 28px;
}
.metrics {
  display: grid;
  grid-template-columns: 1fr;
  padding: 10px 24px;
  transform: rotate(1.2deg);
}
.metrics div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  padding: 24px 0;
}
.metrics div:last-child {
  border: 0;
}
.metrics strong {
  color: #75efd3;
  font-size: 34px;
  letter-spacing: -0.05em;
}
.metrics span {
  color: #849e97;
  font-size: 13px;
  font-weight: 700;
}
.content {
  padding-top: 72px;
}
.section-heading h2 {
  margin: 7px 0 4px;
  font-size: 30px;
}
.section-heading p {
  margin: 0;
  color: #829c95;
}
.toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 160px auto;
  gap: 10px;
  margin: 22px 0;
  padding: 12px;
}
.search {
  display: flex;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(3, 13, 11, 0.62);
  padding: 0 12px;
}
.search:focus-within {
  border-color: #27d8b4;
  box-shadow: 0 0 0 3px rgba(39, 216, 180, 0.1);
}
.search svg {
  width: 18px;
  color: #66817a;
}
.search input {
  width: 100%;
  border: 0;
  outline: 0;
  padding: 10px;
  background: transparent;
  color: #e8f5f1;
  font-size: 14px;
}
.blog-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
  margin-top: 18px;
}
@media (max-width: 960px) {
  .hero-inner {
    grid-template-columns: 1fr;
    gap: 28px;
  }
  .metrics {
    grid-template-columns: repeat(3, 1fr);
  }
  .metrics div {
    display: grid;
    justify-items: center;
    border-right: 1px solid var(--border);
    border-bottom: 0;
  }
  .blog-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 640px) {
  .hero-inner {
    padding-top: 48px;
    padding-bottom: 48px;
  }
  .hero h1 {
    font-size: 38px;
  }
  .metrics {
    grid-template-columns: 1fr;
  }
  .metrics div {
    display: flex;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
  .toolbar {
    grid-template-columns: 1fr;
  }
  .blog-grid {
    grid-template-columns: 1fr;
  }
}
</style>
