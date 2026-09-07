import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  { path: '/', name: 'Home', component: () => import('../views/Home.vue'), meta: { title: '博客首页' } },
  { path: '/blog/new', name: 'CreateBlog', component: () => import('../views/BlogEditor.vue'), meta: { title: '新建博客', requiresAuth: true } },
  { path: '/blog/:id/edit', name: 'EditBlog', component: () => import('../views/BlogEditor.vue'), meta: { title: '编辑博客', requiresAuth: true } },
  { path: '/blog/:id', name: 'BlogDetail', component: () => import('../views/BlogDetail.vue'), props: true, meta: { title: '博客详情' } },
  { path: '/agent', name: 'AgentWorkspace', component: () => import('../views/UnifiedAgent.vue'), meta: { title: 'AI 助手', requiresAuth: true } },
  { path: '/agent/operations', name: 'OperationsCenter', component: () => import('../views/OperationsCenter.vue'), meta: { title: '运营中心', requiresAuth: true, requiresAdmin: true } },
  { path: '/me', name: 'MySpace', component: () => import('../views/MySpace.vue'), meta: { title: '个人中心', requiresAuth: true } },
  { path: '/admin', name: 'AdminDashboard', component: () => import('../views/AdminDashboard.vue'), meta: { title: '管理后台', requiresAuth: true, requiresAdmin: true } },
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { title: '登录', guestOnly: true } },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue'), meta: { title: '注册', guestOnly: true } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFound.vue'), meta: { title: '页面未找到' } },
];

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) });

router.beforeEach((to) => {
  const token = localStorage.getItem('authToken');
  const user = JSON.parse(localStorage.getItem('currentUser') || 'null');
  document.title = `${to.meta.title || '博客平台'} · Yu Like`;
  if (to.meta.guestOnly && token) return '/';
  if (to.meta.requiresAuth && !token) return { path: '/login', query: { redirect: to.fullPath } };
  if (to.meta.requiresAdmin && String(user?.role || '').toUpperCase() !== 'ADMIN') return '/';
  return true;
});

export default router;
