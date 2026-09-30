import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('./components/AppShell.vue'),
    children: [
      { path: '', name: 'dashboard', component: () => import('./views/DashboardView.vue'), meta: { title: 'ภาพรวมลานจอด' } },
      { path: 'demo', name: 'demo', component: () => import('./views/DemoView.vue'), meta: { title: 'Demo Mode: ลานจอดจำลอง + Backend Debug' } },
      { path: 'gate', name: 'gate', component: () => import('./views/GateView.vue'), meta: { title: 'บันทึกรถเข้า–ออก' } },
      { path: 'history', name: 'history', component: () => import('./views/HistoryView.vue'), meta: { title: 'ประวัติการจอด' } },
      { path: 'reports', name: 'reports', component: () => import('./views/ReportsView.vue'), meta: { title: 'รายงานรายได้', role: 'manager' } },
      { path: 'slots', name: 'slots', component: () => import('./views/SlotsView.vue'), meta: { title: 'จัดการช่องจอด', role: 'manager' } },
      { path: 'users', name: 'users', component: () => import('./views/UsersView.vue'), meta: { title: 'ผู้ใช้งาน', role: 'owner' } },
      { path: 'settings', name: 'settings', component: () => import('./views/SettingsView.vue'), meta: { title: 'ตั้งค่าลานและค่าจอด', role: 'owner' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuth()
  await auth.restore()
  if (to.meta.public) return auth.isLoggedIn && to.name === 'login' ? '/' : true
  if (!auth.isLoggedIn) return { name: 'login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} }
  if (to.meta.role && !auth.can(to.meta.role)) return '/'
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · Smart Parking` : 'Smart Parking Dashboard'
})

export default router
