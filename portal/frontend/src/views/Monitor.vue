<template>
  <div class="page">
    <div class="glass-card page-header">
      <div>
        <h3 class="page-title">系统监控</h3>
        <p class="page-desc">平台服务运行状态</p>
      </div>
      <a-button @click="refreshAll"><template #icon><icon-refresh /></template> 刷新</a-button>
    </div>

    <!-- 服务状态卡片 -->
    <div class="service-grid">
      <div v-for="svc in services" :key="svc.name" class="glass-card service-card">
        <div class="service-top">
          <div class="service-icon" :style="{ background: svc.bg }">
            <component :is="svc.icon" style="font-size: 20px;" :style="{ color: svc.color }" />
          </div>
          <div class="status-cell">
            <span class="status-dot" :class="svc.online ? 'online' : 'offline'"></span>
            <span :style="{ color: svc.online ? '#00B42A' : '#F53F3F' }">{{ svc.online ? '运行中' : '已停止' }}</span>
          </div>
        </div>
        <h4 class="service-name">{{ svc.name }}</h4>
        <p class="service-desc">{{ svc.desc }}</p>
        <div class="service-meta">
          <span class="mono">端口: {{ svc.port }}</span>
          <a-button v-if="svc.path" type="text" size="mini" @click="openPath(svc.path)">访问</a-button>
        </div>
      </div>
    </div>

    <!-- DS 资源监控 -->
    <div class="glass-card ds-monitor-section" style="margin-top: 16px;">
      <h3 class="section-title">调度引擎资源监控</h3>
      <div v-if="dsMonitor.healthy" class="ds-monitor-grid">
        <div class="monitor-item">
          <div class="monitor-label">CPU 使用率</div>
          <a-progress
            :percent="dsMonitor.cpuUsage / 100"
            :color="progressColor(dsMonitor.cpuUsage)"
            :show-text="false"
            size="large"
          />
          <div class="monitor-value" :style="{ color: valueColor(dsMonitor.cpuUsage) }">{{ dsMonitor.cpuUsage }}%</div>
        </div>
        <div class="monitor-item">
          <div class="monitor-label">内存使用率</div>
          <a-progress
            :percent="dsMonitor.memoryUsage / 100"
            :color="progressColor(dsMonitor.memoryUsage)"
            :show-text="false"
            size="large"
          />
          <div class="monitor-value" :style="{ color: valueColor(dsMonitor.memoryUsage) }">
            {{ dsMonitor.memoryUsage }}%
            <span class="monitor-sub">（{{ formatBytes(dsMonitor.memoryUsed) }} / {{ formatBytes(dsMonitor.memoryMax) }}）</span>
          </div>
        </div>
        <div class="monitor-meta">
          <div class="meta-item">
            <span class="meta-label">Master</span>
            <span class="meta-value" :class="dsMonitor.masterStatus === 'UP' ? 'text-success' : 'text-danger'">{{ dsMonitor.masterStatus }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Worker</span>
            <span class="meta-value" :class="dsMonitor.workerStatus === 'UP' ? 'text-success' : 'text-danger'">{{ dsMonitor.workerStatus }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">数据库</span>
            <span class="meta-value" :class="dsMonitor.dbStatus === 'UP' ? 'text-success' : 'text-danger'">{{ dsMonitor.dbStatus }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">运行模式</span>
            <span class="meta-value">Standalone</span>
          </div>
        </div>
      </div>
      <div v-else class="ds-unavailable">
        <span class="status-dot offline"></span>
        调度引擎服务不可用
      </div>
    </div>

    <!-- 服务器信息 -->
    <div class="glass-card info-section" style="margin-top: 16px;">
      <h3 class="section-title">服务器信息</h3>
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="操作系统">Ubuntu 22.04 LTS</a-descriptions-item>
        <a-descriptions-item label="CPU">8 核</a-descriptions-item>
        <a-descriptions-item label="内存">14 GB</a-descriptions-item>
        <a-descriptions-item label="磁盘">49 GB SSD</a-descriptions-item>
        <a-descriptions-item label="Docker">v29.4.3</a-descriptions-item>
        <a-descriptions-item label="Swap">8 GB</a-descriptions-item>
      </a-descriptions>
    </div>

    <!-- 部署架构 -->
    <div class="glass-card info-section" style="margin-top: 16px;">
      <h3 class="section-title">部署架构</h3>
      <a-descriptions :column="1" bordered>
        <a-descriptions-item label="Nginx">反向代理 &middot; 端口 80 (唯一对外端口)</a-descriptions-item>
        <a-descriptions-item label="Portal Frontend">Vue3 + Arco Design (科技蓝白风)</a-descriptions-item>
        <a-descriptions-item label="Portal Backend">FastAPI &middot; 内部端口 8000</a-descriptions-item>
        <a-descriptions-item label="DolphinScheduler">Standalone 模式 &middot; 内部端口 12345</a-descriptions-item>
        <a-descriptions-item label="MySQL 8.0">元数据库 &middot; 内部端口 3306</a-descriptions-item>
        <a-descriptions-item label="Redis 7">缓存 &middot; 内部端口 6379</a-descriptions-item>
      </a-descriptions>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { IconRefresh, IconLink, IconCalendar, IconApps, IconStorage, IconComputer } from '@arco-design/web-vue/es/icon'
import { getDSMonitor, getSystemServices } from '../api'

// 视觉属性按 service.key 映射 (后端只返回 key/name/desc/port/online)
const visualMap: Record<string, any> = {
  'nginx':            { bg: 'rgba(43,90,237,0.08)',  color: '#2B5AED', icon: IconApps,     path: '/' },
  'portal-frontend':  { bg: 'rgba(43,90,237,0.08)',  color: '#2B5AED', icon: IconComputer, path: '/' },
  'portal-backend':   { bg: 'rgba(0,201,167,0.08)',  color: '#00C9A7', icon: IconStorage,  path: '/api/health' },
  'dolphinscheduler': { bg: 'rgba(255,125,0,0.08)',  color: '#FF7D00', icon: IconCalendar, path: '' },
  'mysql':            { bg: 'rgba(43,90,237,0.06)',  color: '#2B5AED', icon: IconLink,     path: '' },
  'redis':            { bg: 'rgba(245,63,63,0.06)',  color: '#F53F3F', icon: IconStorage,  path: '' },
}

const services = ref<any[]>([])

async function loadServices() {
  try {
    const res: any = await getSystemServices()
    services.value = (res.services || []).map((s: any) => ({
      ...s,
      ...(visualMap[s.key] || { bg: 'rgba(0,0,0,0.05)', color: '#86909C', icon: IconApps, path: '' }),
    }))
  } catch {
    services.value = []
  }
}

const dsMonitor = reactive({
  healthy: false,
  cpuUsage: 0,
  memoryUsage: 0,
  memoryMax: 0,
  memoryUsed: 0,
  masterStatus: '-',
  workerStatus: '-',
  dbStatus: '-',
})

function progressColor(val: number) {
  if (val < 60) return '#00B42A'
  if (val < 80) return '#FF7D00'
  return '#F53F3F'
}

function valueColor(val: number) {
  if (val < 60) return '#00B42A'
  if (val < 80) return '#FF7D00'
  return '#F53F3F'
}

function formatBytes(bytes: number) {
  if (!bytes) return '-'
  const gb = bytes / (1024 * 1024 * 1024)
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / (1024 * 1024)).toFixed(0)} MB`
}

async function loadDSMonitor() {
  try {
    const res: any = await getDSMonitor()
    Object.assign(dsMonitor, res)
  } catch {
    dsMonitor.healthy = false
  }
}

function refreshAll() {
  loadServices()
  loadDSMonitor()
}

function openPath(path: string) {
  window.open(path, '_blank')
}

onMounted(() => { loadServices(); loadDSMonitor() })
</script>

<style scoped>
.page { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.page-header { padding: 20px 24px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 18px; font-weight: 600; color: #1D2129; }
.page-desc { margin: 4px 0 0; font-size: 13px; color: #86909C; }
.section-title { margin: 0 0 16px; font-size: 15px; font-weight: 600; color: #1D2129; }

.service-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.service-card { padding: 20px; }
.service-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.service-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
.service-name { margin: 0 0 4px; font-size: 15px; font-weight: 600; color: #1D2129; }
.service-desc { margin: 0 0 12px; font-size: 12px; color: #86909C; }
.service-meta { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #86909C; border-top: 1px solid #E5E8ED; padding-top: 12px; }
.mono { font-family: 'JetBrains Mono', monospace; }

.status-cell { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; }
.status-dot.online { background: #00B42A; box-shadow: 0 0 6px rgba(0,180,42,0.3); }
.status-dot.offline { background: #F53F3F; box-shadow: 0 0 6px rgba(245,63,63,0.3); }

/* DS 资源监控 */
.ds-monitor-section { padding: 20px; }
.ds-monitor-grid { display: flex; flex-direction: column; gap: 20px; }
.monitor-item { display: flex; align-items: center; gap: 16px; }
.monitor-label { font-size: 13px; color: #4E5969; min-width: 80px; flex-shrink: 0; }
.monitor-item :deep(.arco-progress) { flex: 1; }
.monitor-value { font-size: 15px; font-weight: 600; min-width: 120px; text-align: right; }
.monitor-sub { font-size: 12px; font-weight: 400; color: #86909C; }

.monitor-meta {
  display: flex; gap: 32px; padding-top: 16px;
  border-top: 1px solid #E5E8ED;
}
.meta-item { display: flex; flex-direction: column; gap: 4px; }
.meta-label { font-size: 12px; color: #86909C; }
.meta-value { font-size: 13px; font-weight: 600; color: #1D2129; }
.text-success { color: #00B42A; }
.text-danger { color: #F53F3F; }

.ds-unavailable {
  display: flex; align-items: center; gap: 8px;
  color: #86909C; font-size: 13px; padding: 12px 0;
}

.info-section { padding: 20px; }

@media (max-width: 1200px) { .service-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
