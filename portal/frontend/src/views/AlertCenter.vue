<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getDSInstances, rerunDSInstance } from '../api'

interface AlertItem {
  id: number
  name: string
  state: string
  startTime: string
  duration: string
  handled: boolean
}

const router = useRouter()
const items = ref<AlertItem[]>([])
const loading = ref(false)
const filter = ref('')

const FILTER_TABS = [
  { label: '全部异常', value: '' },
  { label: '运行失败', value: 'FAILURE' },
  { label: '已终止', value: 'KILL' },
  { label: '停止', value: 'STOP' },
]

const STATE_MAP: Record<string, { text: string; color: string; bg: string; icon: string }> = {
  FAILURE: { text: '运行失败', color: '#f53f3f', bg: '#ffece8', icon: '✕' },
  KILL:    { text: '已终止',  color: '#ff7d00', bg: '#fff7e8', icon: '⊘' },
  STOP:    { text: '已停止',  color: '#86909c', bg: '#f2f3f5', icon: '■' },
}

const filtered = computed(() =>
  filter.value ? items.value.filter(i => i.state === filter.value) : items.value
)

const kpi = computed(() => ({
  total: items.value.length,
  failure: items.value.filter(i => i.state === 'FAILURE').length,
  other: items.value.filter(i => i.state !== 'FAILURE').length,
}))

onMounted(() => loadAlerts())

async function loadAlerts() {
  loading.value = true
  try {
    // 拉取失败/终止/停止的实例
    const [r1, r2, r3] = await Promise.all([
      getDSInstances({ pageNo: 1, pageSize: 30, stateType: 'FAILURE' }) as any,
      getDSInstances({ pageNo: 1, pageSize: 10, stateType: 'KILL' }) as any,
      getDSInstances({ pageNo: 1, pageSize: 10, stateType: 'STOP' }) as any,
    ])
    const all = [
      ...(r1.list || []),
      ...(r2.list || []),
      ...(r3.list || []),
    ]
    // 按时间倒序
    all.sort((a: any, b: any) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())
    items.value = all.map((item: any) => ({
      id: item.id,
      name: item.name || `工作流-${item.processDefinitionCode || item.id}`,
      state: item.state,
      startTime: item.startTime ? formatTime(item.startTime) : '-',
      duration: item.duration != null ? formatDuration(item.duration) : '-',
      handled: false,
    }))
  } catch (e: any) {
    Message.error('加载失败：' + (e?.message || '未知错误'))
  } finally { loading.value = false }
}

async function handleRerun(id: number) {
  try {
    await rerunDSInstance(id)
    Message.success('已触发重跑')
    const item = items.value.find(i => i.id === id)
    if (item) item.handled = true
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '重跑失败')
  }
}

function goDetail(id: number) {
  router.push(`/ops/instances/${id}`)
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatDuration(s: number): string {
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return m < 60 ? `${m}m${s % 60}s` : `${Math.floor(m / 60)}h${m % 60}m`
}
</script>

<template>
  <div class="alert-page">
    <!-- KPI -->
    <div class="kpi-row">
      <div class="kpi-card kpi-card--fail">
        <div class="kpi-value">{{ kpi.total }}</div>
        <div class="kpi-label">近期异常</div>
      </div>
      <div class="kpi-card kpi-card--fail">
        <div class="kpi-value">{{ kpi.failure }}</div>
        <div class="kpi-label">运行失败</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value">{{ kpi.other }}</div>
        <div class="kpi-label">其他异常</div>
      </div>
      <div class="kpi-card kpi-card--ok">
        <div class="kpi-value">{{ items.filter(i => i.handled).length }}</div>
        <div class="kpi-label">已处理</div>
      </div>
    </div>

    <!-- 筛选 + 刷新 -->
    <div class="filter-bar">
      <div class="filter-tabs">
        <span v-for="tab in FILTER_TABS" :key="tab.value"
          class="filter-tab" :class="{ active: filter === tab.value }"
          @click="filter = tab.value">
          {{ tab.label }}
          <span v-if="tab.value === 'FAILURE'" class="tab-count">{{ kpi.failure }}</span>
        </span>
      </div>
      <a-button size="mini" @click="loadAlerts" :loading="loading">刷新</a-button>
    </div>

    <!-- 告警列表 -->
    <div class="alert-list">
      <div v-if="loading && !filtered.length" class="list-empty"><a-spin /></div>
      <div v-else-if="!filtered.length" class="list-empty">
        <a-empty description="暂无异常记录" />
      </div>
      <div v-else class="alert-cards">
        <div v-for="item in filtered" :key="item.id"
          class="alert-card" :class="{ 'alert-card--handled': item.handled }">
          <div class="alert-card__left">
            <span class="alert-icon" :style="{ color: STATE_MAP[item.state]?.color || '#86909c' }">
              {{ STATE_MAP[item.state]?.icon || '!' }}
            </span>
          </div>
          <div class="alert-card__body">
            <div class="alert-name">{{ item.name }}</div>
            <div class="alert-meta">
              <span class="alert-state-badge"
                :style="{ color: STATE_MAP[item.state]?.color, background: STATE_MAP[item.state]?.bg }">
                {{ STATE_MAP[item.state]?.text || item.state }}
              </span>
              <span class="alert-time">{{ item.startTime }}</span>
              <span class="alert-duration">耗时 {{ item.duration }}</span>
              <span v-if="item.handled" class="alert-handled">✓ 已处理</span>
            </div>
          </div>
          <div class="alert-card__actions">
            <a-button type="text" size="mini" @click="goDetail(item.id)">查看详情</a-button>
            <a-button type="outline" size="mini" status="danger"
              @click="handleRerun(item.id)" :disabled="item.handled">
              重跑
            </a-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.alert-page { padding: 20px; display: flex; flex-direction: column; gap: 16px; }

.kpi-row { display: flex; gap: 12px; }
.kpi-card { flex: 1; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px; }
.kpi-card--fail { border-left: 3px solid #f53f3f; }
.kpi-card--ok   { border-left: 3px solid #00b42a; }
.kpi-value { font-size: 28px; font-weight: 700; color: #1d2129; }
.kpi-label { font-size: 12px; color: #86909c; margin-top: 4px; }

.filter-bar { display: flex; align-items: center; justify-content: space-between; }
.filter-tabs { display: flex; gap: 4px; }
.filter-tab { padding: 5px 14px; font-size: 13px; cursor: pointer; border-radius: 4px; color: #4e5969; transition: all 0.15s; display: flex; align-items: center; gap: 5px; }
.filter-tab:hover { background: #f0f5ff; color: #165dff; }
.filter-tab.active { background: #165dff; color: #fff; }
.tab-count { background: rgba(255,255,255,0.3); border-radius: 8px; padding: 0 5px; font-size: 11px; }
.filter-tab:not(.active) .tab-count { background: #f2f3f5; color: #86909c; }

.list-empty { display: flex; align-items: center; justify-content: center; height: 200px; }
.alert-cards { display: flex; flex-direction: column; gap: 10px; }

.alert-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 16px; display: flex; align-items: center; gap: 16px;
  transition: box-shadow 0.15s;
}
.alert-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.alert-card--handled { opacity: 0.6; }
.alert-card__left { flex-shrink: 0; }
.alert-icon { font-size: 22px; font-weight: 700; }
.alert-card__body { flex: 1; min-width: 0; }
.alert-name { font-size: 15px; font-weight: 600; color: #1d2129; margin-bottom: 6px; }
.alert-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.alert-state-badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 500; }
.alert-time { font-size: 12px; color: #86909c; }
.alert-duration { font-size: 12px; color: #86909c; }
.alert-handled { font-size: 12px; color: #00b42a; font-weight: 500; }
.alert-card__actions { display: flex; gap: 8px; flex-shrink: 0; }
</style>
