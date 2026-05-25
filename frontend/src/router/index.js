import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
  },
  {
    path: '/interview/:id',
    name: 'Interview',
    component: () => import('@/views/Interview.vue'),
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/History.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
const publicRoutes = ['/', '/login', '/register']

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (!token && !publicRoutes.includes(to.path)) {
    next('/login')
  } else if (token && (to.path === '/login' || to.path === '/register')) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
