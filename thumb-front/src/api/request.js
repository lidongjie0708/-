import axios from 'axios';
import { useUserStore } from '../stores/user';

let activeRequests = 0;
const beginRequest = () => {
  activeRequests += 1;
  document.body.classList.add('api-loading');
};
const endRequest = () => {
  activeRequests = Math.max(0, activeRequests - 1);
  if (activeRequests === 0) document.body.classList.remove('api-loading');
};

const request = axios.create({
  baseURL: '/api',
  timeout: 12000,
  withCredentials: true,
  paramsSerializer: {
    serialize(params) {
      return Object.entries(params || {})
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
        .join('&');
    },
  },
});

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  beginRequest();
  return config;
});

request.interceptors.response.use(
  (response) => {
    endRequest();
    return response;
  },
  (error) => {
    endRequest();
    if (error.response?.status === 401) {
      const userStore = useUserStore();
      userStore.clearUser();
      if (!['/login', '/register'].includes(window.location.pathname)) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export const pythonAgentRequest = axios.create({
  baseURL: '/py-agent',
  timeout: 60000,
});

pythonAgentRequest.interceptors.request.use((config) => {
  const token = localStorage.getItem('aiToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

pythonAgentRequest.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const userStore = useUserStore();
      userStore.clearAgentToken();
    }
    return Promise.reject(error);
  },
);

export function unwrapResponse(response) {
  const body = response?.data;
  if (!body || body.code !== 0) throw new Error(body?.message || '请求失败');
  return body.data;
}

export const get = (url, params = {}) => request({ method: 'get', url, params });
export const post = (url, data = {}) => request({ method: 'post', url, data });
export const put = (url, data = {}, params = {}) => request({ method: 'put', url, data, params });
export const del = (url, params = {}) => request({ method: 'delete', url, params });

export default request;
