<template>
  <article class="blog-card section-card">
    <router-link class="cover" :to="`/blog/${blog.id}`"
      ><img
        v-if="cover && !imageFailed"
        :src="cover"
        :alt="blog.title"
        loading="lazy"
        @error="imageFailed = true" />
      <div v-else class="cover-placeholder">
        <svg viewBox="0 0 24 24" fill="none">
          <path
            d="M5 4h14v16H5V4Zm3 4h8m-8 4h8m-8 4h5"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
          />
        </svg></div
    ></router-link>
    <div class="body">
      <div class="meta">
        <span>{{ formatDate(blog.createTime, 'YYYY-MM-DD') }}</span
        ><span>{{ estimateReadMinutes(blog.content) }} 分钟阅读</span>
      </div>
      <router-link :to="`/blog/${blog.id}`"
        ><h3 class="line-clamp-2">{{ blog.title }}</h3></router-link
      >
      <p class="line-clamp-3">
        {{ blog.summary || truncateString(blog.content, 130) }}
      </p>
      <div v-if="tags.length" class="tags">
        <span v-for="tag in tags.slice(0, 3)" :key="tag">{{ tag }}</span>
      </div>
    </div>
    <footer>
      <span class="author">{{ getAuthorName(blog) }}</span
      ><ThumbButton
        :blog-id="blog.id"
        :count="Number(blog.thumbCount) || 0"
        :has-thumb="Boolean(blog.hasThumb)"
      />
    </footer>
  </article>
</template>
<script setup>
import { computed, ref } from 'vue'
import ThumbButton from './ThumbButton.vue'
import {
  estimateReadMinutes,
  formatDate,
  getAuthorName,
  getBlogCover,
  truncateString,
} from '../utils'
const props = defineProps({ blog: { type: Object, required: true } })
const imageFailed = ref(false)
const cover = computed(() => getBlogCover(props.blog))
const tags = computed(() =>
  String(props.blog.tags || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean)
)
</script>
<style scoped>
.blog-card {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  transition:
    transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1),
    border-color 0.35s,
    box-shadow 0.35s;
}
.blog-card:hover {
  transform: translateY(-7px);
  border-color: rgba(39, 216, 180, 0.34);
  box-shadow: 0 30px 70px rgba(0, 0, 0, 0.38);
}
.cover {
  display: block;
  aspect-ratio: 16/9;
  overflow: hidden;
  background: #10211d;
}
.cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(0.88) contrast(1.04);
  transition:
    transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1),
    filter 0.3s;
}
.blog-card:hover .cover img {
  transform: scale(1.06);
  filter: saturate(1.08) contrast(1.04);
}
.cover-placeholder {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  background:
    radial-gradient(
      circle at 70% 20%,
      rgba(39, 216, 180, 0.18),
      transparent 35%
    ),
    linear-gradient(145deg, #10241f, #0a1714);
  color: #38d7b4;
}
.cover-placeholder svg {
  width: 38px;
}
.body {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: 18px;
}
.meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: #728c85;
  font-size: 11px;
  font-weight: 700;
}
.body h3 {
  margin: 10px 0 8px;
  color: #eef8f5;
  font-size: 19px;
  line-height: 1.4;
}
.body p {
  margin: 0;
  color: #8da59f;
  font-size: 14px;
  line-height: 1.7;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}
.tags span {
  border-radius: 999px;
  border: 1px solid rgba(135, 218, 198, 0.1);
  background: rgba(255, 255, 255, 0.04);
  padding: 3px 8px;
  color: #91aaa4;
  font-size: 10px;
  font-weight: 750;
}
footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--border);
  padding: 12px 18px;
}
.author {
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #abc0ba;
  font-size: 12px;
  font-weight: 750;
}
</style>
