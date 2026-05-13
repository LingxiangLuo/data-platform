import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue'),
    },
    {
      path: '/',
      component: () => import('../layouts/BasicLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('../views/Dashboard.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'datasources',
          name: 'DataSources',
          component: () => import('../views/DataSource.vue'),
          meta: { title: '数据源管理' },
        },
        {
          path: 'sync-tasks',
          name: 'SyncTasks',
          component: () => import('../views/SyncTask.vue'),
          meta: { title: '数据同步' },
        },
        {
          path: 'sql-dev',
          name: 'SqlDev',
          component: () => import('../views/SqlDev.vue'),
          meta: { title: '代码开发' },
        },
        {
          path: 'workflows/:id/edit',
          name: 'WorkflowEditor',
          component: () => import('../views/WorkflowEditor.vue'),
          meta: { title: '编辑工作流', hideLayout: true },
        },
        {
          path: 'components',
          name: 'Components',
          component: () => import('../views/Component.vue'),
          meta: { title: '组件管理' },
        },
        {
          path: 'workflows',
          name: 'Workflows',
          component: () => import('../views/Workflow.vue'),
          meta: { title: '工作流开发' },
        },
        {
          path: 'scheduler',
          redirect: '/scheduler/history',
        },
        {
          path: 'scheduler/tasks',
          redirect: '/workflows',
        },
        {
          path: 'scheduler/history',
          name: 'RunInstances',
          component: () => import('../views/SchedulerHistory.vue'),
          meta: { title: '运行实例' },
        },
        {
          path: 'alerts',
          name: 'Alerts',
          component: () => import('../views/SchedulerTasks.vue'),
          meta: { title: '告警通知' },
        },
        {
          path: 'data-assets',
          name: 'DataAssets',
          component: () => import('../views/DataAssets.vue'),
          meta: { title: '数据表' },
        },
        {
          path: 'field-assets',
          name: 'FieldAssets',
          component: () => import('../views/FieldAssets.vue'),
          meta: { title: '字段资产' },
        },
        {
          path: 'lineage',
          name: 'DataLineage',
          component: () => import('../views/DataLineage.vue'),
          meta: { title: '数据血缘' },
        },
        {
          path: 'monitor',
          name: 'Monitor',
          component: () => import('../views/Monitor.vue'),
          meta: { title: '系统监控' },
        },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
