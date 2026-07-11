import { defineStore } from 'pinia'
import { userApi } from '../api/services'

export const useUserStore = defineStore('user', {
  state: () => ({
    currentUser: JSON.parse(localStorage.getItem('currentUser') || 'null'),
    authToken: localStorage.getItem('authToken') || '',
    aiToken: localStorage.getItem('aiToken') || '',
    aiTokenExpiresAt: Number(localStorage.getItem('aiTokenExpiresAt')) || 0,
    loading: false,
    error: '',
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.authToken && state.currentUser),
    getUserId: (state) => state.currentUser?.id,
    getUsername: (state) =>
      state.currentUser?.username || state.currentUser?.userName,
    role: (state) => state.currentUser?.role || 'USER',
    displayName: (state) =>
      state.currentUser?.username || state.currentUser?.userName || '用户',
  },
  actions: {
    persistAuth(data) {
      this.authToken = data.token
      this.currentUser = data.user
      localStorage.setItem('authToken', data.token)
      localStorage.setItem('currentUser', JSON.stringify(data.user))
    },
    async login({ username, password }) {
      if (!username || !password) {
        this.error = '请输入用户名和密码'
        return false
      }
      this.loading = true
      this.error = ''
      try {
        const response = await userApi.login({ username, password })
        if (response.data?.code === 0 && response.data.data?.token) {
          this.persistAuth(response.data.data)
          return true
        }
        this.error = response.data?.message || '登录失败，请检查用户名和密码'
        return false
      } catch (error) {
        this.error =
          error.response?.data?.message || '无法连接登录服务，请稍后重试'
        return false
      } finally {
        this.loading = false
      }
    },
    async register({ username, password, email }) {
      if (!username || !password || !email) {
        this.error = '请填写用户名、密码和邮箱'
        return false
      }
      this.loading = true
      this.error = ''
      try {
        const response = await userApi.register({ username, password, email })
        if (response.data?.code === 0) return true
        this.error = response.data?.message || '注册失败'
        return false
      } catch (error) {
        this.error =
          error.response?.data?.message || '无法连接注册服务，请稍后重试'
        return false
      } finally {
        this.loading = false
      }
    },
    async ensureAgentToken() {
      if (this.aiToken && this.aiTokenExpiresAt > Date.now() + 30_000)
        return this.aiToken
      this.clearAgentToken()
      const response = await userApi.createAgentToken()
      if (response.data?.code === 0 && response.data.data?.token) {
        this.aiToken = response.data.data.token
        this.aiTokenExpiresAt =
          Date.now() + (Number(response.data.data.expiresIn) || 300) * 1000
        localStorage.setItem('aiToken', this.aiToken)
        localStorage.setItem('aiTokenExpiresAt', String(this.aiTokenExpiresAt))
        return this.aiToken
      }
      throw new Error(response.data?.message || '获取 Agent Token 失败')
    },
    async updateProfile(payload) {
      const response = await userApi.updateProfile(payload)
      if (response.data?.code !== 0)
        throw new Error(response.data?.message || '资料更新失败')
      this.currentUser = response.data.data
      localStorage.setItem('currentUser', JSON.stringify(this.currentUser))
      return this.currentUser
    },
    clearAgentToken() {
      this.aiToken = ''
      this.aiTokenExpiresAt = 0
      localStorage.removeItem('aiToken')
      localStorage.removeItem('aiTokenExpiresAt')
    },
    async logout() {
      try {
        if (this.authToken) await userApi.logout()
      } catch {}
      this.clearUser()
    },
    clearUser() {
      this.currentUser = null
      this.authToken = ''
      this.error = ''
      this.clearAgentToken()
      localStorage.removeItem('authToken')
      localStorage.removeItem('currentUser')
    },
    restoreLogin() {
      return this.isLoggedIn
    },
  },
})
