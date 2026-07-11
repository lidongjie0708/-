<template>
  <div v-if="loading" class="loader-wrapper" :class="{ fullscreen }">
    <div class="loader-box">
      <span class="spinner"></span>
      <span class="message">{{ message }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  fullscreen: {
    type: Boolean,
    default: false,
  },
  message: {
    type: String,
    default: '正在加载...',
  },
});
</script>

<style scoped>
.loader-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 2rem;
}

.fullscreen {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(247, 248, 251, 0.72);
  backdrop-filter: blur(6px);
}

.loader-box {
  display: inline-flex;
  align-items: center;
  gap: 0.8rem;
  border: 1px solid #d9e0ea;
  border-radius: 999px;
  background: #fff;
  padding: 0.75rem 1rem;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12);
}

.spinner {
  width: 1.2rem;
  height: 1.2rem;
  border: 3px solid #ccfbf1;
  border-top-color: #0f766e;
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

.message {
  color: #475569;
  font-size: 0.9rem;
  font-weight: 700;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
