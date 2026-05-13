<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getDSInstances, getDSWorkflows, getDSInstanceTasks, getDSTaskLog, rerunDSInstance } from '../api'

interface Instance {
  id: number; name: string; state: string; startTime: string; endTime: string; duration: string; workflowName?: string
}
interface Task {
  id: number; name: string; state: string; startTime: string; endTime: string; duration: string
}

const workflows = ref<any[]>([])
const instances = ref<Instance[]>([])
const loading = ref(false)
const selectedWf = ref<number | null>(null)
const statusFilter = ref('')
const dateRange = ref<string[]>([])
const wfSearch = ref('')
const expandedKeys = ref<number[]>([])
const taskMap = ref<Record<number, Task[]>>({})
const logVisible = ref(false)
const logContent = ref('')
const logLoading = ref(false)

const filteredWorkflows = computed(() => {
  if (!wfSearch.value) return workflows.value
  return workflows.value.filter((w: any) => w.name.toLowerCase().includes(wfSearch.value.toLowerCase()))
})

onMounted(async () => {
  await Promise.all([loadWorkflows(), loadInstances()])
})

async function loadWorkflows() {
  try {
    const res: any = await getDSWorkflows()
    workflows.value = res.items || res || []
  } catch { workflows.value = [] }
}

async function loadInstances() {
  loading.value = true
  try {
    const params: any = { page: 1, page_size: 50 }
    if (statusFilter.value) params.state = statusFilter.value
    if (selectedWf.value) params.workflow_code = selectedWf.value
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res: any = await getDSInstances(params)
    instances.value = res.items || res || []
  } catch { instances.value = [] }
  finally { loading.value = false }
}

function selectWorkflow(code: number | null) {
  selectedWf.value = code
  loadInstances()
}

function setStatus(s: string) {
  statusFilter.value = s
  loadInstances()
}

async function expandRow(id: number) {
  if (taskMap.value[id]) return
  try {
    const res: any = await getDSInstanceTasks(id)
    taskMap.value[id] = res.items || res || []
  } catch { taskMap.value[id] = [] }
}

async function viewLog(taskId: number) {
  logLoading.value = true
  logVisible.value = true
  try {
    const res: any = await getDSTaskLog(taskId)
    logContent.value = res.log || res.message || '无日志'
  } catch { logContent.value = '获取日志失败' }
  finally { logLoading.value = false }
}

async function rerun(instanceId: number) {
  try {
    await rerunDSInstance(instanceId)
    Message.success('已触发重跑')
    loadInstances()
  } catch { Message.error('重跑失败') }
}

function stateColor(state: string): string {
  const map: Record<string, string> = { SUCCESS: '#00b42a', FAILURE: '#f53f3f', RUNNING_EXECUTION: '#165dff', STOP: '#86909c' }
  return map[state] || '#86909c'
}
function stateText(state: string): string {
  const map: Record<string, string> = { SUCCESS: '成功', FAILURE: '失败', RUNNING_EXECUTION: '运行中', STOP: '停止' }
  return map[state] || state
}
</script>

<template>
  <div class="history-page">
    <div class="history-page__sidebar">
      <div class="sidebar__header">工作流</div>
      <input v-model="wfSearch" placeholder="搜索..." class="sidebar__search" />
      <div class="sidebar__list">
        <div class="sidebar__item" :class="{ active: !selectedWf }" @click="selectWorkflow(null)">全部</div>
        <div v-for="wf in filteredWorkflows" :key="wf.code || wf.id"
          class="sidebar__item" :class="{ active: selectedWf === (wf.code || wf.id) }"
          @click="selectWorkflow(wf.code || wf.id)">
          {{ wf.name }}
        </div>
      </div>
    </div>
    <div class="history-page__main">
      <div class="main__filters">
        <div class="filter-tabs">
          <span class="tab" :class="{ active: !statusFilter }" @click="setStatus('')">全部</span>
          <span class="tab" :class="{ active: statusFilter === 'SUCCESS' }" @click="setStatus('SUCCESS')">成功</span>
          <span class="tab" :class="{ active: statusFilter === 'FAILURE' }" @click="setStatus('FAILURE')">失败</span>
          <span class="tab" :class="{ active: statusFilter === 'RUNNING_EXECUTION' }" @click="setStatus('RUNNING_EXECUTION')">运行中</span>
        </div>
        <a-range-picker v-model="dateRange" style="width: 240px;" @change="loadInstances" />
      </div>
      <a-table :data="instances" :loading="loading" :pagination="false" row-key="id"
        :expandable="{ expandedRowKeys: expandedKeys }"
        @expand="(id: any) => { expandedKeys.push(id); expandRow(id) }">
        <template #columns>
          <a-table-column title="工作流" data-index="name" />
          <a-table-column title="状态" data-index="state">
            <template #cell="{ record }">
              <span :style="{ color: stateColor(record.state), fontWeight: '600' }">{{ stateText(record.state) }}</span>
            </template>
          </a-table-column>
          <a-table-column title="开始时间" data-index="startTime" />
          <a-table-column title="结束时间" data-index="endTime" />
          <a-table-column title="耗时" data-index="duration" />
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-button type="text" size="mini" @click="rerun(record.id)">重跑</a-button>
            </template>
          </a-table-column>
        </template>
        <template #expand-row="{ record }">
          <div class="subtask-list" v-if="taskMap[record.id]">
            <div v-for="task in taskMap[record.id]" :key="task.id" class="subtask-item">
              <span class="subtask-name">{{ task.name }}</span>
              <span :style="{ color: stateColor(task.state) }">{{ stateText(task.state) }}</span>
              <span class="subtask-duration">{{ task.duration }}</span>
              <a-button type="text" size="mini" @click="viewLog(task.id)">日志</a-button>
            </div>
          </div>
        </template>
      </a-table>
    </div>
    <a-modal v-model:visible="logVisible" title="任务日志" :width="720" :footer="false">
      <div class="log-content">
        <a-spin :loading="logLoading" style="width:100%">
          <pre class="log-pre">{{ logContent }}</pre>
        </a-spin>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.history-page { display: flex; height: calc(100vh - 60px); }
.history-page__sidebar { width: 240px; border-right: 1px solid #e5e7eb; display: flex; flex-direction: column; background: #fafbfc; }
.sidebar__header { padding: 16px; font-weight: 600; font-size: 14px; border-bottom: 1px solid #e5e7eb; }
.sidebar__search { margin: 8px 12px; padding: 6px 10px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; outline: none; }
.sidebar__search:focus { border-color: #165dff; }
.sidebar__list { flex: 1; overflow-y: auto; padding: 4px 8px; }
.sidebar__item { padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; margin: 2px 0; transition: all 0.15s; }
.sidebar__item:hover { background: #f0f5ff; }
.sidebar__item.active { background: #e8f3ff; color: #165dff; font-weight: 500; }
.history-page__main { flex: 1; display: flex; flex-direction: column; padding: 16px; overflow: auto; }
.main__filters { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.filter-tabs { display: flex; gap: 8px; }
.tab { padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; background: #f2f3f5; transition: all 0.15s; }
.tab:hover { background: #e8f3ff; }
.tab.active { background: #165dff; color: #fff; }
.subtask-list { padding: 8px 16px; }
.subtask-item { display: flex; align-items: center; gap: 16px; padding: 6px 0; border-bottom: 1px solid #f2f3f5; font-size: 13px; }
.subtask-name { flex: 1; font-weight: 500; }
.subtask-duration { color: #86909c; min-width: 60px; }
.log-content { max-height: 500px; overflow: auto; }
.log-pre { font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 6px; }
</style>