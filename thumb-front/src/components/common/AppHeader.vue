<template>
  <header class="site-header">
    <div class="container-custom header-inner">
      <router-link class="brand" to="/" aria-label="Yu Like 首页"
        ><span class="brand-mark">Y</span
        ><span
          ><strong>Yu Like</strong><small>Blogs & AI</small></span
        ></router-link
      >
      <button
        class="menu-button"
        type="button"
        :aria-expanded="open"
        @click="open = !open"
      >
        <svg viewBox="0 0 24 24" fill="none">
          <path
            d="M4 7h16M4 12h16M4 17h16"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          /></svg
        ><span class="sr-only">打开导航</span>
      </button>
      <div :class="['nav-wrap', { open }]">
        <nav aria-label="主导航">
          <router-link to="/" @click="open = false">首页</router-link>
          <router-link
            v-if="userStore.isLoggedIn"
            to="/me"
            @click="open = false"
            >个人中心</router-link
          >
          <router-link
            v-if="userStore.isLoggedIn"
            to="/agent"
            @click="open = false"
            >AI 助手</router-link
          >
          <router-link v-if="isAdmin" to="/admin" @click="open = false"
            >管理后台</router-link
          >
        </nav>
        <LoginBadge />
      </div>
    </div>
  </header>
</template>
<script setup>
import { computed, ref } from 'vue'
import LoginBadge from './LoginBadge.vue'
import { useUserStore } from '../../stores/user'
const userStore = useUserStore()
const open = ref(false)
const isAdmin = computed(() => String(userStore.role).toUpperCase() === 'ADMIN')
</script>
<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 40;
  border-bottom: 1px solid var(--border);
  background: rgba(5, 15, 13, 0.72);
  backdrop-filter: blur(22px) saturate(130%);
}
.header-inner,
.nav-wrap,
nav,
.brand {
  display: flex;
  align-items: center;
}
.header-inner {
  height: 74px;
  justify-content: space-between;
}
.brand {
  gap: 10px;
}
.brand-mark {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border: 1px solid rgba(112, 255, 222, 0.35);
  border-radius: 13px;
  background: linear-gradient(145deg, #36e4bd, #0d806b);
  color: #03110e;
  box-shadow: 0 9px 28px rgba(39, 216, 180, 0.2);
  font-weight: 950;
}
.brand > span:last-child {
  display: grid;
}
.brand strong {
  color: #eef8f5;
  font-size: 16px;
  line-height: 1.15;
}
.brand small {
  color: #6f8c84;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.nav-wrap {
  gap: 24px;
}
nav {
  gap: 6px;
}
nav a {
  position: relative;
  border-radius: 10px;
  padding: 9px 12px;
  color: #8ca49e;
  font-size: 14px;
  font-weight: 750;
}
nav a:hover,
nav a.router-link-exact-active {
  background: rgba(39, 216, 180, 0.08);
  color: #69ebcd;
}
nav a.router-link-exact-active::after {
  position: absolute;
  right: 12px;
  bottom: 3px;
  left: 12px;
  height: 2px;
  border-radius: 999px;
  background: #27d8b4;
  content: "";
}
.menu-button {
  display: none;
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  border-radius: 11px;
  background: rgba(255,255,255,.04);
  color: #a9beb8;
}
.menu-button svg {
  width: 20px;
  margin: auto;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
@media (max-width: 760px) {
  .menu-button {
    display: block;
  }
  .nav-wrap {
    display: none;
    position: absolute;
    top: 74px;
    left: 0;
    right: 0;
    align-items: stretch;
    border-bottom: 1px solid var(--border);
    background: rgba(7, 17, 15, 0.97);
    padding: 14px 20px;
    box-shadow: 0 22px 50px rgba(0, 0, 0, 0.35);
  }
  .nav-wrap.open {
    display: grid;
  }
  nav {
    align-items: stretch;
    flex-direction: column;
  }
  .nav-wrap :deep(.login-badge) {
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }
}
</style>
