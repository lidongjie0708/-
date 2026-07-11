<template>
  <div class="app-shell">
    <router-view />
  </div>
</template>

<style>
body {
  min-width: 320px;
  min-height: 100vh;
  background: var(--page);
  color: var(--text);
}

.app-shell {
  min-height: 100vh;
}
</style>
