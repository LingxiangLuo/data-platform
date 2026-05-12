<template>
  <div class="page">
    <div class="glass-card page-header">
      <div>
        <h3 class="page-title">运行记录</h3>
        <p class="page-desc">调度执行历史与运维</p>
      </div>
      <a-space>
        <a-range-picker v-model="dateRange" style="width: 240px;" @change="loadInstances" />
        <a-button @click="loadInstances"><template #icon><icon-refresh /></template> 刷新</a-button>
      </a-space>
    </div>

    <!-- 日历热力图 -->
    <div class="glass-card calendar-section">
      <h3 class="section-title">近 30 天执行概览</h3>
      <div class="calendar-grid">
        <div v-for="day in calendarData" :key="day.date"
          class="calendar-cell" :class="calendarClass(day)"
          :title="`${day.date}: 成功${day.success} 失败${day.failure} 共${day.total}`"
          @click="selectDate(day.date)">
          <span class="cell-date">{{ day.date.split('-')[2] }}</span>
        </div>
      </div>
      <div class="calendar-legend">
        <span class="legend-label">少</span>
        <span class="legend-cell" style="background:#ebedf0"></span>
        <span class="legend-cell" style="background:#9be9a8"></span>
        <span class="legend-cell" style="background:#40c463"></span>
        <span class="legend-cell" style="background:#30a14e"></span>
        <span class="legend-cell" style="background:#216e39"></span>
        <span class="legend-label">多</span>
        <span style="margin-left:12px; font-size:11px; color:#86909C">
          <span class="legend-cell" style="background:#ffeef0; border:1px solid #F53F3F"></span> 有失败
        </span>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-tabs">
      <div class="tab-item" :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</div>
      <div class="tab-item" :class="{ active: filter === 'SUCCESS' }" @click="filter = 'SUCCESS'">成功</div>
      <div class="tab-item failure" :class="{ active: filter === 'FAILURE' }" @click="filter = 'FAILURE'">失败</div>
      <div class="tab-item running" :class="{ active: filter === 'RUNNING' }" @click="filter = 'RUNNING'">运行中</div>
      <div v-if="selectedDate" class="tab-item" style="cursor:default; color:#2B5AED;">
        {{ selectedDate }} <span @click.stop="clearDate" style="cursor:pointer; margin-left:4px">✕</span>
      </div>
    </div>

    <!-- 实例表格 -->
    <div class="glass-card table-card">
      <a-table :data="filteredList" :pagination="false" :loading="loading" :bordered="false" stripe>
        <template #columns>
          <a-table-column title="工作流" data-index="name" :width="180">
            <template #cell="{ record }">
              <span class="wf-name">{{ record.name }}</span>
            </template>
          </a-table-column>
          <a-table-column title="状态" :width="90">
            <template #cell="{ record }">
              <a-tag v-if="record.state === 'SUCCESS'" color="green" size="small">成功</a-tag>
              <a-tag v-else-if="record.state === 'FAILURE'" color="red" size="small">失败</a-tag>
              <a-tag v-else-if="record.state === 'RUNNING'" color="blue" size="small">运行中</a-tag>
              <a-tag v-else color="gray" size="small">{{ record.state }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="开始时间" data-index="startTime" :width="160">
            <template #cell="{ record }">
              <span class="mono">{{ record.startTime }}</span>
            </template>
          </a-table-column>
          <a-table-column title="结束时间" data-index="endTime" :width="160">
            <template #cell="{ record }">
              <span class="mono">{{ record.endTime || '—' }}</span>
            </template>
          </a-table-column>
          <a-table-column title="耗时" :width="100">
            <template #cell="{ record }">
              <span class="mono">{{ formatDuration(record.duration) }}</span>
            </template>
          </a-table-column>
          <a-table-column title="操作" :width="140" fixed="right">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="mini" @click="toggleDetail(record)">
                  {{ expandedId === record.id ? '收起' : '详情' }}
                </a-button>
                <a-button v-if="record.state === 'FAILURE'" type="text" size="mini" status="danger" @click="rerunInstance(record)">重跑</a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
        <template #expand-row="{ record }">
          <!-- 任务详情 -->
          <div class="task-detail" v-if="expandedId === record.id">
            <div v-if="taskLoading" style="padding:16px; text-align:center;">
              <a-spin :size="20" />
            </div>
            <table v-else class="task-table">
              <tr v-for="task in tasks" :key="task.id" :class="{ 'task-fail': task.state === 'FAILURE' }">
                <td class="task-status-cell">
                  <span v-if="task.state === 'SUCCESS'" style="color:#00B42A">✓</span>
                  <span v-else-if="task.state === 'FAILURE'" style="color:#F53F3F">✗</span>
                  <span v-else style="color:#2B5AED">●</span>
                </td>
                <td class="task-name">{{ task.name }}</td>
                <td>
                  <a-tag v-if="task.state === 'SUCCESS'" color="green" size="small">成功</a-tag>
                  <a-tag v-else-if="task.state === 'FAILURE'" color="red" size="small">失败</a-tag>
                  <a-tag v-else color="blue" size="small">{{ task.state }}</a-tag>
                </td>
                <td class="mono">{{ task.startTime }} → {{ task.endTime || '—' }}</td>
                <td class="mono">{{ formatDuration(task.duration) }}</td>
                <td>
                  <a-button type="text" size="mini" @click="openLog(task)">日志</a-button>
                  <a-button v-if="task.state === 'FAILURE'" type="text" size="mini" status="danger" @click="rerunInstance(record)">重跑</a-button>
                </td>
              </tr>
            </table>
            <!-- 耗时趋势迷你图 -->
            <div v-if="historyDurations.length > 1" class="duration-trend">
              <span class="trend-label">耗时趋势：</span>
              <svg viewBox="0 0 200 30" class="trend-svg">
                <polyline :points="trendPoints" fill="none" stroke="#2B5AED" stroke-width="1.5" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
        </template>
        <template #empty>
          <div class="empty-state">暂无运行记录</div>
        </template>
      </a-table>
    </div>

    <!-- 日志模态框 -->
    <a-modal v-model:visible="logVisible" :title="`任务日志 - ${logTaskName}`" :width="900" :footer="false">
      <div class="log-container">
        <pre class="log-content" v-html="logContent"></pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconRefresh } from '@arco-design/web-vue/es/icon'
import { getDSInstances, getDSCalendar, getDSInstanceTasks, getDSTaskLog, rerunDSInstance } from '../api'

interface CalendarDay {
  date: string
  total: number
  success: number
  failure: number
  rate: number | null
}

interface Instance {
  id: number
  processDefinitionCode: number
  name: string
  state: string
  startTime: string
  endTime: string | null
  duration: number | null
}

const loading = ref(false)
const instances = ref<Instance[]>([])
const calendarData = ref<CalendarDay[]>([])
const dateRange = ref<string[]>([])
const selectedDate = ref('')
const filter = ref('all')

const filteredList = computed(() => {
  let list = instances.value
  if (filter.value !== 'all') list = list.filter(i => i.state === filter.value)
  return list
})

// 日历热力图
function calendarClass(day: CalendarDay) {
  if (day.failure > 0) return 'has-failure'
  if (day.total === 0) return 'empty'
  if (day.rate === 1) return 'rate-4'
  if (day.rate > 0.8) return 'rate-3'
  if (day.rate > 0.5) return 'rate-2'
  return 'rate-1'
}

function selectDate(date: string) {
  selectedDate.value = date
  loadInstances()
}

function clearDate() {
  selectedDate.value = ''
  loadInstances()
}

// 格式化
function formatDuration(sec: number | null) {
  if (sec == null) return '—'
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`
}

// 任务详情
const expandedId = ref<number | null>(null)
const tasks = ref<any[]>([])
const taskLoading = ref(false)
const historyDurations = ref<number[]>([])

const trendPoints = computed(() => {
  const data = historyDurations.value
  if (data.length < 2) return ''
  const max = Math.max(...data, 1)
  return data.map((v, i) => `${(i / (data.length - 1)) * 200},${30 - (v / max) * 25}`).join(' ')
})

async function toggleDetail(record: Instance) {
  if (expandedId.value === record.id) {
    expandedId.value = null
    tasks.value = []
    return
  }
  expandedId.value = record.id
  taskLoading.value = true
  try {
    tasks.value = await getDSInstanceTasks(record.id) || []
    // 加载该工作流的历史耗时
    const histRes: any = await getDSInstances({
      pageSize: 20,
      processDefinitionCode: record.processDefinitionCode,
    })
    historyDurations.value = (histRes?.list || [])
      .filter((i: any) => i.duration != null)
      .reverse()
      .map((i: any) => i.duration)
  } catch {}
  taskLoading.value = false
}

// 日志
const logVisible = ref(false)
const logTaskName = ref('')
const logContent = ref('')

async function openLog(task: any) {
  logTaskName.value = task.name
  logVisible.value = true
  logContent.value = '<span style="color:#86909C">加载中...</span>'
  try {
    const res: any = await getDSTaskLog(task.id)
    let text = res?.log || '暂无日志'
    // 关键字高亮
    text = text.replace(/ERROR/gi, '<span style="color:#F53F3F;font-weight:bold">ERROR</span>')
    text = text.replace(/WARN(?:ING)?/gi, '<span style="color:#FF7D00;font-weight:bold">$&</span>')
    logContent.value = text
  } catch {
    logContent.value = '<span style="color:#F53F3F">获取日志失败</span>'
  }
}

// 重跑
async function rerunInstance(record: Instance) {
  Modal.confirm({
    title: '确认重跑',
    content: `确定要重跑「${record.name}」吗？`,
    onOk: async () => {
      try {
        await rerunInstanceAction(record.id)
        Message.success('已触发重跑')
        loadInstances()
      } catch {}
    },
  })
}

async function rerunInstanceAction(instanceId: number) {
  await rerunDSInstance(instanceId)
}

// 加载数据
async function loadInstances() {
  loading.value = true
  const params: any = { pageSize: 50 }
  if (selectedDate.value) {
    params.startDate = `${selectedDate.value} 00:00:00`
    params.endDate = `${selectedDate.value} 23:59:59`
  } else if (dateRange.value.length === 2) {
    params.startDate = `${dateRange.value[0]} 00:00:00`
    params.endDate = `${dateRange.value[1]} 23:59:59`
  }
  try {
    const res: any = await getDSInstances(params)
    instances.value = res?.list || []
  } catch {}
  loading.value = false
}

async function loadCalendar() {
  try {
    calendarData.value = await getDSCalendar(30) || []
  } catch {}
}

onMounted(() => {
  loadInstances()
  loadCalendar()
})
</script>

<style scoped>
.page { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.page-header { padding: 20px 24px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 18px; font-weight: 600; color: #1D2129; }
.page-desc { margin: 4px 0 0; font-size: 13px; color: #86909C; }
.section-title { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #1D2129; }

/* 日历热力图 */
.calendar-section { padding: 20px; margin-bottom: 16px; }
.calendar-grid {
  display: flex; flex-wrap: wrap; gap: 3px;
}
.calendar-cell {
  width: 24px; height: 24px; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: outline 0.15s;
  outline: 2px solid transparent;
}
.calendar-cell:hover { outline: 2px solid #2B5AED; }
.calendar-cell.empty { background: #ebedf0; }
.calendar-cell.rate-1 { background: #9be9a8; }
.calendar-cell.rate-2 { background: #40c463; }
.calendar-cell.rate-3 { background: #30a14e; }
.calendar-cell.rate-4 { background: #216e39; }
.calendar-cell.has-failure { background: #ffeef0; outline: 1px solid #F53F3F; }
.cell-date { font-size: 10px; color: #4E5969; }
.calendar-cell.rate-3 .cell-date, .calendar-cell.rate-4 .cell-date { color: #fff; }
.calendar-legend {
  display: flex; align-items: center; gap: 3px; margin-top: 8px;
}
.legend-label { font-size: 11px; color: #86909C; margin: 0 4px; }
.legend-cell { width: 12px; height: 12px; border-radius: 2px; }

/* 筛选 */
.filter-tabs { display: flex; gap: 4px; margin-bottom: 16px; }
.tab-item {
  padding: 6px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;
  color: #4E5969; background: #F7F8FA; transition: all 0.15s;
}
.tab-item:hover { background: #EFF4FF; color: #2B5AED; }
.tab-item.active { background: #2B5AED; color: #FFFFFF; }
.tab-item.failure.active { background: #F53F3F; }
.tab-item.running.active { background: #165DFF; }

/* 表格 */
.table-card { padding: 0; overflow: hidden; }
.wf-name { font-weight: 500; color: #1D2129; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.empty-state { padding: 40px 0; text-align: center; color: #86909C; }

/* 任务详情 */
.task-detail { padding: 12px 0; }
.task-table { width: 100%; font-size: 13px; border-collapse: collapse; }
.task-table td { padding: 6px 12px; vertical-align: middle; }
.task-table tr { border-bottom: 1px solid #F2F3F5; }
.task-table tr:hover { background: #F7F8FA; }
.task-fail { background: #FFF2F0; }
.task-status-cell { width: 24px; text-align: center; }
.task-name { font-weight: 500; color: #1D2129; }

.duration-trend {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; margin-top: 8px;
  background: #F7F8FA; border-radius: 6px;
}
.trend-label { font-size: 12px; color: #86909C; flex-shrink: 0; }
.trend-svg { width: 200px; height: 30px; }

/* 日志 */
.log-container { max-height: 60vh; overflow: auto; background: #1e1e1e; border-radius: 6px; }
.log-content {
  padding: 16px; margin: 0;
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 12px; line-height: 1.6;
  color: #d4d4d4; white-space: pre-wrap; word-break: break-all;
}

:deep(.arco-table-th) { background: #FAFBFC !important; }
</style>
