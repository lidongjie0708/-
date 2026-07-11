<template>
  <div class="login-badge">
    <template v-if="userStore.isLoggedIn"
      ><router-link class="identity" to="/me"
        ><span class="avatar">{{ avatarText }}</span
        ><span
          ><strong>{{ userStore.displayName }}</strong
          ><small>{{ userStore.role }}</small></span
        ></router-link
      ><button
        class="logout"
        type="button"
        :disabled="busy"
        @click="logout"
        aria-label="退出登录"
      >
        <svg viewBox="0 0 24 24" fill="none">
          <path
            d="M10 5H5v14h5m4-3 4-4-4-4m4 4H9"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg></button></template
    ><template v-else
      ><router-link class="login-link" to="/login">登录</router-link
      ><router-link class="btn btn-primary" to="/register"
        >注册</router-link
      ></template
    >
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
const router = useRouter(),
  userStore = useUserStore(),
  busy = ref(false)
const avatarText = computed(() =>
  String(userStore.displayName || 'U')
    .slice(0, 1)
    .toUpperCase()
)
async function logout() {
  busy.value = true
  await userStore.logout()
  busy.value = false
  router.push('/')
}
</script>
<style scoped>
.login-badge,
.identity {
  display: flex;
  align-items: center;
}
.login-badge {
  gap: 10px;
}
.identity {
  gap: 8px;
}
.avatar {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 50%;
  border: 1px solid rgba(39, 216, 180, 0.22);
  background: rgba(39, 216, 180, 0.12);
  color: #63e5c7;
  font-size: 13px;
  font-weight: 900;
}
.identity > span:last-child {
  display: grid;
}
.identity strong {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
}
.identity small {
  color: #6f8982;
  font-size: 9px;
  font-weight: 800;
}
.logout {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: #829b95;
}
.logout:hover {
  border-color: rgba(251, 113, 133, 0.35);
  background: rgba(251, 113, 133, 0.08);
  color: #fb7185;
}
.logout svg {
  width: 17px;
}
.login-link {
  color: #a7bbb6;
  font-size: 14px;
  font-weight: 750;
}
.login-link:hover {
  color: #63e5c7;
}
</style>
