<template>
  <main class="page-shell">
    <AppHeader />
    <div class="container-custom detail">
      <div class="back-row">
        <button class="back" @click="goBack">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              d="m15 18-6-6 6-6"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            /></svg
          >返回
        </button>
      </div>
      <ApiLoader
        :loading="blogStore.loading && !blog"
        message="正在加载文章…"
      /><ErrorAlert :message="blogStore.error" /><template v-if="blog"
        ><article class="article section-card">
          <div v-if="cover && !imageFailed" class="hero-image">
            <img :src="cover" :alt="blog.title" @error="imageFailed = true" />
          </div>
          <div class="article-body">
            <div class="meta">
              <span>{{ getAuthorName(blog) }}</span
              ><span>{{ formatDate(blog.createTime) }}</span
              ><span>{{ estimateReadMinutes(blog.content) }} 分钟阅读</span>
            </div>
            <h1>{{ blog.title }}</h1>
            <p v-if="blog.summary" class="summary">{{ blog.summary }}</p>
            <div v-if="tags.length" class="tags">
              <span v-for="tag in tags" :key="tag">{{ tag }}</span>
            </div>
            <div class="actions">
              <ThumbButton
                :blog-id="blog.id"
                :count="Number(blog.thumbCount) || 0"
                :has-thumb="Boolean(blog.hasThumb)"
              /><button class="btn btn-outline" @click="copyLink">
                <svg viewBox="0 0 24 24" fill="none">
                  <path
                    d="M9 15 15 9m-4-2 1.2-1.2a4 4 0 0 1 5.7 5.7L16.5 13m-3.5 4-1.2 1.2a4 4 0 1 1-5.7-5.7L7.5 11"
                    stroke="currentColor"
                    stroke-width="1.7"
                    stroke-linecap="round"
                  /></svg
                >{{ copied ? '已复制' : '复制链接' }}
              </button>
            </div>
            <div
              v-if="blog.contentFormat === 'MARKDOWN'"
              class="prose markdown-body"
              v-html="renderedContent"
            ></div>
            <div v-else class="prose">
              <p v-for="(paragraph, index) in paragraphs" :key="index">
                {{ paragraph }}
              </p>
            </div>
          </div>
        </article>
        <CommentSection :blog-id="blog.id" />
        <section v-if="relatedBlogs.length" class="related">
          <div class="related-head">
            <h2>继续阅读</h2>
            <router-link to="/">查看全部</router-link>
          </div>
          <div class="related-grid">
            <BlogCard
              v-for="item in relatedBlogs"
              :key="item.id"
              :blog="item"
            />
          </div></section></template
      ><EmptyState
        v-else-if="!blogStore.loading"
        title="文章不存在"
        description="它可能已被删除或暂时不可访问。"
        ><router-link class="btn btn-primary" to="/"
          >返回首页</router-link
        ></EmptyState
      >
    </div>
  </main>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '../components/common/AppHeader.vue'
import ApiLoader from '../components/common/ApiLoader.vue'
import ErrorAlert from '../components/common/ErrorAlert.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ThumbButton from '../components/ThumbButton.vue'
import CommentSection from '../components/CommentSection.vue'
import BlogCard from '../components/BlogCard.vue'
import { useBlogStore } from '../stores/blog'
import { useThumbStore } from '../stores/thumb'
import {
  estimateReadMinutes,
  formatDate,
  getAuthorName,
  getBlogCover,
} from '../utils'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
const props = defineProps({ id: { type: String, required: true } })
const router = useRouter(),
  blogStore = useBlogStore(),
  thumbStore = useThumbStore()
const copied = ref(false),
  imageFailed = ref(false)
const blogId = computed(() => String(props.id))
const blog = computed(() => blogStore.getBlogById(blogId.value))
const cover = computed(() => getBlogCover(blog.value || {}))
const tags = computed(() =>
  String(blog.value?.tags || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean)
)
const paragraphs = computed(() =>
  String(blog.value?.content || '')
    .split(/\n{2,}/)
    .map((x) => x.trim())
    .filter(Boolean)
)
const renderedContent = computed(() =>
  DOMPurify.sanitize(marked.parse(String(blog.value?.content || '')))
)
const relatedBlogs = computed(() =>
  blogStore.blogs
    .filter((x) => String(x.id) !== blogId.value)
    .sort((a, b) => (Number(b.thumbCount) || 0) - (Number(a.thumbCount) || 0))
    .slice(0, 3)
)
function goBack() {
  window.history.length > 1 ? router.back() : router.push('/')
}
async function copyLink() {
  await navigator.clipboard?.writeText(location.href)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}
async function load() {
  imageFailed.value = false
  await blogStore.fetchBlogDetail(blogId.value, true)
  if (blog.value)
    thumbStore.setThumbStatus(blog.value.id, Boolean(blog.value.hasThumb))
}
onMounted(async () => {
  await Promise.all([blogStore.fetchBlogs(), load()])
})
watch(blogId, load)
</script>
<style scoped>
.detail {
  max-width: 1050px;
  padding-top: 20px;
}
.back-row {
  margin-bottom: 14px;
}
.back {
  display: flex;
  align-items: center;
  gap: 5px;
  border: 0;
  background: none;
  color: #64748b;
  padding: 6px 0;
  font-size: 13px;
  font-weight: 750;
}
.back:hover {
  color: #0f766e;
}
.back svg,
.actions svg {
  width: 17px;
}
.article {
  overflow: hidden;
}
.hero-image {
  max-height: 470px;
  overflow: hidden;
  background: #f1f5f9;
}
.hero-image img {
  width: 100%;
  height: 100%;
  max-height: 470px;
  object-fit: cover;
}
.article-body {
  max-width: 800px;
  margin: auto;
  padding: 54px 28px 64px;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.meta span,
.tags span {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 5px 10px;
  color: #64748b;
  font-size: 11px;
  font-weight: 750;
}
.article h1 {
  margin: 18px 0 14px;
  font-size: clamp(34px, 5vw, 54px);
  line-height: 1.13;
  letter-spacing: -0.035em;
}
.summary {
  border-left: 3px solid #0f766e;
  margin: 20px 0;
  padding-left: 18px;
  color: #475569;
  font-size: 18px;
  line-height: 1.75;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 28px 0 38px;
}
.prose {
  color: #334155;
  font-size: 17px;
  line-height: 1.95;
  white-space: pre-wrap;
}
.prose p {
  margin: 0 0 22px;
}
.related {
  margin-top: 36px;
}
.related-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.related-head h2 {
  margin: 0;
  font-size: 22px;
}
.related-head a {
  color: #0f766e;
  font-size: 13px;
  font-weight: 800;
}
.related-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
@media (max-width: 800px) {
  .related-grid {
    grid-template-columns: 1fr;
  }
  .article-body {
    padding: 36px 20px;
  }
  .article h1 {
    font-size: 36px;
  }
}
</style>
