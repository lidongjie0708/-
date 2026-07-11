import { customRef } from 'vue';

export function formatDate(date, format = 'YYYY-MM-DD HH:mm') {
  if (!date) return '未知时间';
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return '未知时间';

  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');

  return format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes);
}

export function formatNumber(num = 0) {
  const value = Number(num) || 0;
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
}

export function truncateString(str = '', length = 100) {
  const value = String(str || '').trim();
  if (value.length <= length) return value;
  return `${value.slice(0, length)}...`;
}

export function estimateReadMinutes(content = '') {
  const length = String(content || '').trim().length;
  return Math.max(1, Math.ceil(length / 450));
}

export function getBlogCover(blog) {
  return blog?.coverImg || blog?.coverUrl || blog?.image || '';
}

export function getAuthorName(blog) {
  return blog?.authorName || blog?.username || blog?.userName || '社区作者';
}

export function debounce(fn, delay = 300) {
  let timeout = null;
  return function debounced(...args) {
    window.clearTimeout(timeout);
    timeout = window.setTimeout(() => {
      fn.apply(this, args);
      timeout = null;
    }, delay);
  };
}

export function useDebouncedRef(value, delay = 300) {
  let timeout;
  return customRef((track, trigger) => ({
    get() {
      track();
      return value;
    },
    set(newValue) {
      window.clearTimeout(timeout);
      timeout = window.setTimeout(() => {
        value = newValue;
        trigger();
      }, delay);
    },
  }));
}
