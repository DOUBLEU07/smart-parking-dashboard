import { defineStore } from 'pinia'
import { api, getToken, setToken } from '../api'

const RANK = { staff: 1, manager: 2, owner: 3 }

export const useAuth = defineStore('auth', {
  state: () => ({ user: null, token: getToken(), loaded: false }),
  getters: {
    isLoggedIn: (s) => !!s.token && !!s.user,
    can: (s) => (minRole) => !!s.user && RANK[s.user.role] >= RANK[minRole],
  },
  actions: {
    async login(username, password) {
      const res = await api.post('/auth/login', { username, password })
      this.token = res.access_token
      setToken(res.access_token)
      this.user = res.user
      this.loaded = true
    },
    async restore() {
      if (this.loaded) return
      this.loaded = true
      if (!this.token) return
      try {
        this.user = await api.get('/auth/me')
      } catch {
        this.logout()
      }
    },
    logout() {
      this.user = null
      this.token = null
      setToken(null)
    },
  },
})
