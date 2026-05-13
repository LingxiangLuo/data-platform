import axios from 'axios'
import { Message } from '@arco-design/web-vue'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || '请求失败'
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    } else {
      Message.error(msg)
    }
    return Promise.reject(error)
  }
)

// Auth
export const login = (data: { username: string; password: string }) =>
  api.post('/auth/login', data)

export const getMe = () => api.get('/auth/me')

// Dashboard
export const getDashboardStats = () => api.get('/dashboard/stats')

// DataSources
export const getDatasources = (params?: any) => api.get('/datasources', { params })
export const getDatasource = (id: number) => api.get(`/datasources/${id}`)
export const createDatasource = (data: any) => api.post('/datasources', data)
export const updateDatasource = (id: number, data: any) => api.put(`/datasources/${id}`, data)
export const deleteDatasource = (id: number) => api.delete(`/datasources/${id}`)
export const testDatasource = (id: number) => api.post(`/datasources/${id}/test`)

// Sync Tasks
export const getSyncTasks = (params?: any) => api.get('/sync-tasks', { params })
export const getSyncTask = (id: number) => api.get(`/sync-tasks/${id}`)
export const createSyncTask = (data: any) => api.post('/sync-tasks', data)
export const updateSyncTask = (id: number, data: any) => api.put(`/sync-tasks/${id}`, data)
export const deleteSyncTask = (id: number) => api.delete(`/sync-tasks/${id}`)
export const previewSyncTaskDataX = (id: number) => api.get(`/sync-tasks/${id}/preview-datax`)
export const previewSyncTaskUnsaved = (data: any) => api.post('/sync-tasks/preview', data)
export const testSyncTaskConnection = (data: { datasource_id: number; table?: string }) =>
  api.post('/sync-tasks/test-connection', data)
export const runSyncTask = (id: number) => api.post(`/sync-tasks/${id}/run`, undefined, { timeout: 360000 })

// Projects (同步任务分组)
export const getProjects = (params?: any) => api.get('/projects', { params })
export const getProject = (id: number) => api.get(`/projects/${id}`)
export const createProject = (data: any) => api.post('/projects', data)
export const updateProject = (id: number, data: any) => api.put(`/projects/${id}`, data)
export const deleteProject = (id: number, moveTo?: number) =>
  api.delete(`/projects/${id}`, { params: moveTo !== undefined ? { move_to: moveTo } : {} })

// DolphinScheduler 代理
export const getDSWorkflows = (params?: any) => api.get('/ds/workflows', { params })
export const runDSWorkflow = (code: number) => api.post(`/ds/workflows/${code}/run`)
export const onlineDSWorkflow = (code: number) => api.post(`/ds/workflows/${code}/online`)
export const offlineDSWorkflow = (code: number) => api.post(`/ds/workflows/${code}/offline`)
export const rerunDSWorkflow = (code: number) => api.post(`/ds/workflows/${code}/rerun`)
export const complementDSWorkflow = (code: number, startDate: string, endDate: string) =>
  api.post(`/ds/workflows/${code}/complement?start_date=${startDate}&end_date=${endDate}`)
export const getDSInstances = (params?: any) => api.get('/ds/instances', { params })
export const getDSCalendar = (days?: number) => api.get('/ds/instances/calendar', { params: { days } })
export const getDSInstanceTasks = (instanceId: number) => api.get(`/ds/instances/${instanceId}/tasks`)
export const getDSTaskLog = (taskId: number) => api.get(`/ds/tasks/${taskId}/log`)
export const rerunDSInstance = (instanceId: number) => api.post(`/ds/instances/${instanceId}/rerun`)
export const getDSMonitor = () => api.get('/ds/monitor')

// System
export const getSystemServices = () => api.get('/system/services')

// Metadata (元数据简版表)
export const getMetadataTables = (datasource_id: number, keyword?: string, limit = 100) =>
  api.get('/metadata/tables', { params: { datasource_id, keyword, limit } })
export const getMetadataColumns = (datasource_id: number, table: string) => api.get('/metadata/columns', { params: { datasource_id, table } })
export const getMetadataPreview = (datasource_id: number, table: string, limit = 10) => api.get('/metadata/preview', { params: { datasource_id, table, limit } })
export const generateDDL = (data: { datasource_id: number; target_table: string; columns: any[] }) =>
  api.post('/metadata/generate-ddl', data)
export const executeDDL = (data: { datasource_id: number; ddl: string }) =>
  api.post('/metadata/execute-ddl', data)

// Notifications
export const getNotifications = (params?: any) => api.get('/notifications', { params })
export const getUnreadCount = () => api.get('/notifications/unread-count')
export const markNotifRead = (id: number) => api.put(`/notifications/${id}/read`)
export const markAllRead = () => api.put('/notifications/read-all')

// Component Folders
export const getComponentFolders = (type?: string) =>
  api.get('/components/folders', { params: type ? { type } : {} })
export const createComponentFolder = (data: { name: string; type: string; parent_id?: number | null }) =>
  api.post('/components/folders', data)
export const renameComponentFolder = (id: number, name: string) =>
  api.put(`/components/folders/${id}`, { name })
export const deleteComponentFolder = (id: number) =>
  api.delete(`/components/folders/${id}`)

// Components
export const getComponents = (params?: any) => api.get('/components', { params })
export const getComponent = (id: number) => api.get(`/components/${id}`)
export const createComponent = (data: any) => api.post('/components', data)
export const updateComponent = (id: number, data: any) => api.put(`/components/${id}`, data)
export const deleteComponent = (id: number) => api.delete(`/components/${id}`)
export const testComponent = (id: number) => api.post(`/components/${id}/test`)
export const publishComponent = (id: number) => api.post(`/components/${id}/publish`)
export const offlineComponent = (id: number) => api.post(`/components/${id}/offline`)
export const runComponent = (id: number) => api.post(`/components/${id}/run`)
export const runSqlAdhoc = (data: { datasource_id: number; sql: string }) =>
  api.post('/components/run-sql', data, { timeout: 60000 })
export const runComponentScript = (id: number, datasourceId?: number) =>
  api.post(`/components/${id}/run${datasourceId ? `?datasource_id=${datasourceId}` : ''}`, {}, { timeout: 120000 })
export const quickPublishComponent = (id: number) =>
  api.post(`/components/${id}/quick-publish`)
export const setComponentStatus = (id: number, status: string) =>
  api.put(`/components/${id}/status`, { status })
export const resumeComponent = (id: number) =>
  api.post(`/components/${id}/resume`)

// Workflows
export const getWorkflows = (params?: any) => api.get('/workflows', { params })
export const getWorkflow = (id: number) => api.get(`/workflows/${id}`)
export const createWorkflow = (data: any) => api.post('/workflows', data)
export const updateWorkflow = (id: number, data: any) => api.put(`/workflows/${id}`, data)
export const deleteWorkflow = (id: number) => api.delete(`/workflows/${id}`)
export const testWorkflow = (id: number) => api.post(`/workflows/${id}/test`)
export const publishWorkflow = (id: number) => api.post(`/workflows/${id}/publish`)
export const offlineWorkflow = (id: number) => api.post(`/workflows/${id}/offline`)
export const runWorkflow = (id: number) => api.post(`/workflows/${id}/run`)
export const scheduleWorkflowOnline = (id: number) => api.post(`/workflows/${id}/schedule/online`)
export const scheduleWorkflowOffline = (id: number) => api.post(`/workflows/${id}/schedule/offline`)
export const getScheduledWorkflows = () => api.get('/workflows/scheduled')

export default api
