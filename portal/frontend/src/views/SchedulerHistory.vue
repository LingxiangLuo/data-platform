<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getDSInstances, getDSInstanceTasks, getDSTaskLog, rerunDSInstance } from '../api'

interface Instance {
  id: number
  name: string
  state: string
  startTime: string
  endTime: string
  duration: string
}
interface Task {
  id: number
  name: string
  state: string
  startTime: string
  endTime: string
  duration: string
}

const instances = ref<Instance[]>([])
const loading = ref(false)
const statusFilter = ref('')
const dateRange = ref<string[]>([])
const taskMap = ref<Record<number, Task[]>>({})
const taskLoading = ref<Record<number, boolean>>({})
const expandedKeys = ref<number[]>([])
const logVisible = ref(false)
const logContent = ref('')
const logLoading = ref(false)
const autoRefresh = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const STATUS_TABS = [
  { label: '全部', value: '' },
  { label: '成功', value: 'SUCCESS' },
  { label: '失败', value: 'FAILURE' },
  { label: '运行中', value: 'RUNNING_EXECUTION' },
  { label: '停止', value: 'STOP' },
]

const STATE_MAP: Record<string, { text: string; color: string; bg: string }> = {
  SUCCESS:           { text: '成功',  color: '#00b42a', bg: '#e8ffea' },
  FAILURE:           { text: '失败',  color: '#f53f3f', bg: '#ffece8' },
  RUNNING_EXECUTION: { text: '运行中', color: '#165dff', bg: '#e8f3ff' },
  STOP:              { text: '停止',  color: '#86909c', bg: '#f2f3f5' },
  KILL:              { text: '已终止', color: '#ff7d00', bg: '#fff7e8' },
}

onMounted(() => loadInstances())
onUnmounted(() => stopAutoRefresh())

async function loadInstances() {
  loading.value = true
  try {
    const params: Record<string, any> = { pageNo: 1, pageSize: 50 }
    if (statusFilter.value) params.stateType = statusFilter.value
    if (dateRange.value?.length === 2) {
      params.startDate = dateRange.value[0]
      params.endDate = dateRange.value[1]
    }
    const res: any = await getDSInstances(params)
    instances.value = (res.list || res.totalList || res.data?.list || []).map((item: any) => ({
      id: item.id,
      name: item.name || `工作流-${item.processDefinitionCode || item.id}`,
      state: item.state,
      startTime: item.startTime ? formatTime(item.startTime) : '-',
      endTime: item.endTime ? formatTime(item.endTime) : '-',
      duration: item.duration != null ? formatDuration(item.duration) : '-',
    }))
  } catch (e: any) {
    Message.error('加载运行记录失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function setStatus(s: string) {
  statusFilter.value = s
  expandedKeys.value = []
  taskMap.value = {}
  loadInstances()
}

async function toggleExpand(id: number) {
  const idx = expandedKeys.value.indexOf(id)
  if (idx >= 0) {
    expandedKeys.value.splice(idx, 1)
    return
  }
  expandedKeys.value.push(id)
  if (taskMap.value[id]) return
  taskLoading.value[id] = true
  try {
    const res: any = await getDSInstanceTasks(id)
    // DS 返回直接是数组
    const taskList = Array.isArray(res) ? res : (res.taskList || res.list || [])
    taskMap.value[id] = taskList.map((t: any) => ({
      id: t.id,
      name: t.name,
      state: t.state,
      startTime: t.startTime ? formatTime(t.startTime) : '-',
      endTime: t.endTime ? formatTime(t.endTime) : '-',
      duration: t.duration != null ? formatDuration(t.duration) : '-',
    }))
  } catch {
    taskMap.value[id] = []
  } finally {
    taskLoading.value[id] = false
  }
}

async function viewLog(taskId: number) {
  logLoading.value = true
  logVisible.value = true
  logContent.value = ''
  try {
    const res: any = await getDSTaskLog(taskId)
    logContent.value = res.log || res.message || res.data || '暂无日志'
  } catch {
    logContent.value = '获取日志失败'
  } finally {
    logLoading.value = false
  }
}

async function rerun(instanceId: number) {
  try {
    await rerunDSInstance(instanceId)
    Message.success('已触发重跑')
    setTimeout(loadInstances, 1000)
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '重跑失败')
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    timer = setInterval(loadInstances, 30000)
    Message.info('已开启自动刷新（30s）')
  } else {
    stopAutoRefresh()
  }
}

function stopAutoRefresh() {
  if (timer) { clearInterval(timer); timer = null }
  autoRefresh.value = false
}

function formatTime(ts: string | number): string {
  if (!ts) return '-'
  const d = new Date(typeof ts === 'number' ? ts : ts)
  if (isNaN(d.getTime())) return String(ts)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDuration(s: number): string {
  // DS 返回的 duration 单位是秒
  if (s == null || s < 0) return '-'
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m${s % 60}s`
  return `${Math.floor(m / 60)}h${m % 60}m`
}

function stateInfo(state: string) {
  return STATE_MAP[state] || { text: state, color: '#86909c', bg: '#f2f3f5' }
}
</script>

<template>
  <div class="history-page">
    <!-- 页头 -->
    <div class="history-header">
      <div class="history-header__left">
        <h2 class="history-title">运行记录</h2>
        <span class="history-count">共 {{ instances.length }} 条</span>
      </div>
      <div class="history-header__right">
        <a-range-picker
          v-model="dateRange"
          style="width: 260px;"
          @change="loadInstances"
          placeholder="['开始日期', '结束日期']"
        />
        <a-button
          :type="autoRefresh ? 'primary' : 'outline'"
          size="small"
          @click="toggleAutoRefresh"
        >
          {{ autoRefresh ? '● 自动刷新中' : '自动刷新' }}
        </a-button>
        <a-button size="small" @click="loadInstances" :loading="loading">刷新</a-button>
      </div>
    </div>

    <!-- 状态 Tab -->
    <div class="status-tabs">
      <span
        v-for="tab in STATUS_TABS"
        :key="tab.value"
        class="status-tab"
        :class="{ active: statusFilter === tab.value }"
        @click="setStatus(tab.value)"
      >{{ tab.label }}</span>
    </div>

    <!-- 表格 -->
    <div class="history-table-wrap">
      <div v-if="loading && !instances.length" class="history-empty">
        <a-spin />
      </div>
      <div v-else-if="!instances.length" class="history-empty">
        <a-empty description="暂无运行记录" />
      </div>
      <table v-else class="history-table">
        <thead>
          <tr>
            <th style="width:32px"></th>
            <th>工作流名称</th>
            <th style="width:90px">状态</th>
            <th style="width:150px">开始时间</th>
            <th style="width:150px">结束时间</th>
            <th style="width:80px">耗时</th>
            <th style="width:80px">操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="inst in instances" :key="inst.id">
            <!-- 主行 -->
            <tr class="instance-row" @click="toggleExpand(inst.id)">
              <td class="expand-cell">
                <span class="expand-icon" :class="{ expanded: expandedKeys.includes(inst.id) }">▶</span>
              </td>
              <td class="name-cell">{{ inst.name }}</td>
              <td>
                <span class="state-badge" :style="{ color: stateInfo(inst.state).color, background: stateInfo(inst.state).bg }">
                  {{ stateInfo(inst.state).text }}
                </span>
              </td>
              <td class="time-cell">{{ inst.startTime }}</td>
              <td class="time-cell">{{ inst.endTime }}</td>
              <td class="duration-cell">{{ inst.duration }}</td>
              <td @click.stop>
                <a-button type="text" size="mini" @click="rerun(inst.id)">重跑</a-button>
              </td>
            </tr>
            <!-- 展开行：子任务 -->
            <tr v-if="expandedKeys.includes(inst.id)" class="subtask-row">
              <td colspan="7" class="subtask-cell">
                <div v-if="taskLoading[inst.id]" class="subtask-loading"><a-spin size="small" /> 加载中...</div>
                <div v-else-if="!taskMap[inst.id]?.length" class="subtask-empty">暂无子任务</div>
                <table v-else class="subtask-table">
                  <thead>
                    <tr>
                      <th>任务名称</th>
                      <th style="width:90px">状态</th>
                      <th style="width:150px">开始时间</th>
                      <th style="width:80px">耗时</th>
                      <th style="width:60px">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="task in taskMap[inst.id]" :key="task.id" class="subtask-item-row">
                      <td>{{ task.name }}</td>
                      <td>
                        <span class="state-badge state-badge--sm" :style="{ color: stateInfo(task.state).color, background: stateInfo(task.state).bg }">
                          {{ stateInfo(task.state).text }}
                        </span>
                      </td>
                      <td class="time-cell">{{ task.startTime }}</td>
                      <td class="duration-cell">{{ task.duration }}</td>
                      <td>
                        <a-button type="text" size="mini" @click="viewLog(task.id)">日志</a-button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- 日志弹窗 -->
    <a-modal v-model:visible="logVisible" title="任务日志" :width="800" :footer="false">
      <div class="log-modal">
        <a-spin :loading="logLoading" style="width:100%; min-height:200px">
          <pre class="log-pre">{{ logContent || '加载中...' }}</pre>
        </a-spin>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.history-page { padding: 20px; display: flex; flex-direction: column; gap: 0; height: calc(100vh - 60px); overflow: hidden; }

.history-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.history-header__left { display: flex; align-items: baseline; gap: 10px; }
.history-header__right { display: flex; align-items: center; gap: 8px; }
.history-title { margin: 0; font-size: 18px; font-weight: 600; }
.history-count { font-size: 13px; color: #86909c; }

.status-tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid #e5e7eb; padding-bottom: 0; }
.status-tab { padding: 8px 16px; font-size: 13px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; color: #4e5969; transition: all 0.15s; border-radius: 4px 4px 0 0; }
.status-tab:hover { color: #165dff; background: #f0f5ff; }
.status-tab.active { color: #165dff; border-bottom-color: #165dff; font-weight: 500; }

.history-table-wrap { flex: 1; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
.history-empty { display: flex; align-items: center; justify-content: center; height: 200px; }

.history-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.history-table thead tr { background: #f7f8fa; }
.history-table th { padding: 10px 12px; text-align: left; font-weight: 500; color: #4e5969; border-bottom: 1px solid #e5e7eb; white-space: nowrap; }
.history-table td { padding: 10px 12px; border-bottom: 1px solid #f2f3f5; vertical-align: middle; }

.instance-row { cursor: pointer; transition: background 0.1s; }
.instance-row:hover { background: #f7f8fa; }
.expand-cell { text-align: center; }
.expand-icon { display: inline-block; font-size: 10px; color: #86909c; transition: transform 0.2s; }
.expand-icon.expanded { transform: rotate(90deg); }
.name-cell { font-weight: 500; }
.time-cell { color: #4e5969; font-size: 12px; }
.duration-cell { color: #4e5969; font-size: 12px; }

.state-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 500; }
.state-badge--sm { padding: 1px 6px; font-size: 11px; }

.subtask-row { background: #fafbfc; }
.subtask-cell { padding: 0 !important; }
.subtask-loading { padding: 12px 48px; color: #86909c; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.subtask-empty { padding: 12px 48px; color: #86909c; font-size: 13px; }
.subtask-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.subtask-table th { padding: 8px 12px; padding-left: 48px; background: #f2f3f5; color: #86909c; font-weight: 500; text-align: left; }
.subtask-table th:first-child { padding-left: 48px; }
.subtask-item-row td { padding: 8px 12px; border-bottom: 1px solid #f2f3f5; }
.subtask-item-row td:first-child { padding-left: 48px; }
.subtask-item-row:last-child td { border-bottom: none; }

.log-modal { min-height: 200px; }
.log-pre { margin: 0; font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-all; background: #1a1a2e; color: #e2e8f0; padding: 16px; border-radius: 6px; max-height: 500px; overflow-y: auto; font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; }
</style>
