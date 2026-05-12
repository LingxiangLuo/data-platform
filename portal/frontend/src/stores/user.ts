import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, getMe } from '../api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref<any>(null)

  async function login(username: string, password: string) {
    const res: any = await loginApi({ username, password })
    token.value = res.access_token
    userInfo.value = res.user
    localStorage.setItem('token', res.access_token)
    return res
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      const res: any = await getMe()
      userInfo.value = res
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, login, fetchUser, logout }
})
