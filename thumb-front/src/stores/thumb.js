import { defineStore } from 'pinia';
import { thumbApi } from '../api/services';
import { useBlogStore } from './blog';

export const useThumbStore = defineStore('thumb', {
  state: () => ({ thumbedBlogs: new Set(), pendingIds: new Set(), error: '' }),
  getters: {
    hasThumb: (state) => (blogId) => state.thumbedBlogs.has(String(blogId)),
    isPending: (state) => (blogId) => state.pendingIds.has(String(blogId)),
  },
  actions: {
    doThumb(blogId) { return this.toggleThumb(blogId, true); },
    undoThumb(blogId) { return this.toggleThumb(blogId, false); },
    async toggleThumb(blogId, nextStatus) {
      const id = String(blogId);
      if (this.pendingIds.has(id)) return false;
      this.pendingIds.add(id); this.error = '';
      try {
        const response = nextStatus ? await thumbApi.doThumb(id) : await thumbApi.undoThumb(id);
        if (response.data?.code !== 0 || response.data.data !== true) throw new Error(response.data?.message || '点赞操作失败');
        this.setThumbStatus(id, nextStatus);
        useBlogStore().updateBlogThumbStatus(id, nextStatus);
        return true;
      } catch (error) {
        this.error = error.response?.data?.message || error.message || '点赞操作失败，请稍后重试';
        return false;
      } finally { this.pendingIds.delete(id); }
    },
    setThumbStatus(blogId, status) { status ? this.thumbedBlogs.add(String(blogId)) : this.thumbedBlogs.delete(String(blogId)); },
    setMultipleThumbStatus(blogs) { if (Array.isArray(blogs)) blogs.forEach((blog) => this.setThumbStatus(blog.id, Boolean(blog.hasThumb))); },
  },
});
