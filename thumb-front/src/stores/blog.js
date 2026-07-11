import { defineStore } from 'pinia';
import { blogApi } from '../api/services';

export const useBlogStore = defineStore('blog', {
  state: () => ({ blogs: [], blogDetails: {}, loading: false, error: '', isLoaded: false }),
  getters: {
    getBlogById: (state) => (id) => state.blogDetails[String(id)] || state.blogs.find((blog) => String(blog.id) === String(id)),
    totalThumbs: (state) => state.blogs.reduce((sum, blog) => sum + (Number(blog.thumbCount) || 0), 0),
  },
  actions: {
    async fetchBlogs(force = false) {
      if (!force && this.isLoaded && this.blogs.length) return this.blogs;
      this.loading = true; this.error = '';
      try {
        const response = await blogApi.getList();
        if (response.data?.code !== 0) throw new Error(response.data?.message || '文章列表加载失败');
        this.blogs = Array.isArray(response.data.data) ? response.data.data : [];
        this.blogs.forEach((blog) => { if (blog?.id != null) this.blogDetails[String(blog.id)] = blog; });
        this.isLoaded = true; return this.blogs;
      } catch (error) {
        this.error = error.response?.data?.message || error.message || '无法连接文章服务';
        return [];
      } finally { this.loading = false; }
    },
    async fetchBlogDetail(blogId, force = false) {
      const id = String(blogId);
      if (!force && this.blogDetails[id]) return this.blogDetails[id];
      this.loading = true; this.error = '';
      try {
        const response = await blogApi.getDetail(id);
        if (response.data?.code !== 0 || !response.data.data) throw new Error(response.data?.message || '文章不存在');
        const blog = response.data.data;
        this.blogDetails[id] = blog;
        const index = this.blogs.findIndex((item) => String(item.id) === id);
        if (index >= 0) this.blogs[index] = { ...this.blogs[index], ...blog };
        this.addToHistory(id); return blog;
      } catch (error) {
        this.error = error.response?.data?.message || error.message || '文章详情加载失败';
        return null;
      } finally { this.loading = false; }
    },
    addToHistory(blogId) {
      const history = JSON.parse(localStorage.getItem('blogHistory') || '[]');
      localStorage.setItem('blogHistory', JSON.stringify([String(blogId), ...history.filter((id) => String(id) !== String(blogId))].slice(0, 10)));
    },
    getRecentHistory() { return JSON.parse(localStorage.getItem('blogHistory') || '[]'); },
    updateBlogThumbStatus(blogId, hasThumb) {
      const id = String(blogId);
      const update = (blog) => {
        if (!blog || blog.hasThumb === hasThumb) return;
        blog.thumbCount = hasThumb ? (Number(blog.thumbCount) || 0) + 1 : Math.max(0, (Number(blog.thumbCount) || 0) - 1);
        blog.hasThumb = hasThumb;
      };
      update(this.blogDetails[id]); update(this.blogs.find((blog) => String(blog.id) === id));
    },
  },
});
