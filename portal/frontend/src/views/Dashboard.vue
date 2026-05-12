<template>
  <div class="dashboard">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="welcome-left">
        <div class="welcome-accent"></div>
        <div class="welcome-info">
          <h2 class="welcome-title">欢迎回来，{{ userInfo?.real_name || '管理员' }}</h2>
          <p class="welcome-desc">数据中台 MVP &middot; 金融行业离线数据统一工作台</p>
        </div>
      </div>
      <div class="welcome-time">{{ currentTime }}</div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div v-for="(stat, i) in statCards" :key="i" class="stat-card glass-card" :style="{ animationDelay: `${i * 60}ms` }">
        <div class="stat-color-bar" :style="{ background: stat.color }"></div>
        <div class="stat-body">
          <div class="stat-header">
            <span class="stat-label">{{ stat.label }}</span>
          </div>
          <div class="stat-value" :style="{ color: stat.color }">{{ stat.value }}</div>
          <div class="stat-desc">{{ stat.desc }}</div>
        </div>
        <div class="stat-sparkline">
          <svg viewBox="0 0 100 30" preserveAspectRatio="none">
            <defs>
              <linearGradient :id="'grad' + i" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" :stop-color="stat.color" stop-opacity="0.15"/>
                <stop offset="100%" :stop-color="stat.color" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <path :d="stat.sparkline.area" :fill="'url(#grad' + i + ')'" />
            <path :d="stat.sparkline.line" fill="none" :stroke="stat.color" stroke-width="1.5" />
          </svg>
        </div>
      </div>
    </div>

    <!-- 昨日调度概览 -->
    <div class="glass-card overview-section">
      <h3 class="section-title">昨日调度概览</h3>
      <div class="overview-grid">
        <div class="overview-chart">
          <div class="donut-wrap">
            <svg viewBox="0 0 120 120" class="donut-svg">
              <circle cx="60" cy="60" r="50" fill="none" stroke="#F2F3F5" stroke-width="12"/>
              <circle v-if="yesterdayData.total > 0" cx="60" cy="60" r="50" fill="none"
                :stroke="yesterdayData.failure > 0 ? '#F53F3F' : '#00B42A'"
                stroke-width="12" stroke-linecap="round"
                :stroke-dasharray="donutDash" stroke-dashoffset="0"
                transform="rotate(-90 60 60)"/>
            </svg>
            <div class="donut-center">
              <div class="donut-number">{{ yesterdayData.total }}</div>
              <div class="donut-label">总执行</div>
            </div>
          </div>
        </div>
        <div class="overview-details">
          <div class="detail-row">
            <span class="dot success"></span>
            <span class="detail-label">成功</span>
            <span class="detail-value">{{ yesterdayData.success }}</span>
            <span class="detail-pct">{{ yesterdayData.total > 0 ? Math.round(yesterdayData.success / yesterdayData.total * 100) : 0 }}%</span>
          </div>
          <div class="detail-row">
            <span class="dot failure"></span>
            <span class="detail-label">失败</span>
            <span class="detail-value">{{ yesterdayData.failure }}</span>
            <span class="detail-pct">{{ yesterdayData.total > 0 ? Math.round(yesterdayData.failure / yesterdayData.total * 100) : 0 }}%</span>
          </div>
          <div class="detail-row">
            <span class="dot pending"></span>
            <span class="detail-label">待运行</span>
            <span class="detail-value">{{ yesterdayData.pending }}</span>
            <span class="detail-pct">{{ yesterdayData.total > 0 ? Math.round(yesterdayData.pending / yesterdayData.total * 100) : 0 }}%</span>
          </div>
        </div>
        <div class="overview-alert">
          <div v-if="yesterdayData.failure > 0" class="alert-bar failure" @click="$router.push('/scheduler/history')">
            <span>⚠ {{ yesterdayData.failure }} 个工作流执行失败</span>
            <span class="alert-link">查看详情 →</span>
          </div>
          <div v-else-if="yesterdayData.total > 0" class="alert-bar success">
            ✓ 全部执行成功
          </div>
          <div v-else class="alert-bar empty">
            昨日无调度执行
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷入口 + 最近公告 -->
    <div class="content-grid">
      <div class="glass-card quick-section">
        <h3 class="section-title">快捷操作</h3>
        <div class="quick-grid">
          <div v-for="item in quickActions" :key="item.title" class="quick-item" @click="$router.push(item.path)">
            <div class="quick-icon" :style="{ background: item.bg }">
              <component :is="item.icon" style="font-size: 20px;" :style="{ color: item.color }" />
            </div>
            <span class="quick-label">{{ item.title }}</span>
          </div>
        </div>
      </div>

      <div class="glass-card notice-section">
        <h3 class="section-title">系统公告</h3>
        <a-timeline>
          <a-timeline-item v-for="(notice, i) in notices" :key="i" :color="notice.color">
            <div class="notice-row">
              <span class="notice-text">{{ notice.text }}</span>
              <span class="notice-time">{{ notice.time }}</span>
            </div>
          </a-timeline-item>
        </a-timeline>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import { getDashboardStats } from '../api'
import {
  IconLink, IconSync, IconCalendar, IconApps,
} from '@arco-design/web-vue/es/icon'

const userStore = useUserStore()
const userInfo = computed(() => userStore.userInfo)
const currentTime = ref(new Date().toLocaleString('zh-CN'))

const stats = reactive({
  datasource_total: 0, datasource_active: 0,
  task_total: 0, task_active: 0,
  workflow_total: 0,
  yesterday_runs: 0, yesterday_success: 0,
  yesterday_failure: 0, yesterday_pending: 0,
  workflow_trend: [] as number[],
})

const yesterdayData = computed(() => ({
  total: stats.yesterday_runs,
  success: stats.yesterday_success,
  failure: stats.yesterday_failure,
  pending: stats.yesterday_pending,
}))

// 圆环图弧长计算
const donutDash = computed(() => {
  const d = yesterdayData.value
  if (d.total === 0) return '0 314'
  const circumference = 2 * Math.PI * 50
  const successRatio = d.success / d.total
  const successLen = successRatio * circumference
  return `${successLen} ${circumference}`
})

function genSparkline(data: number[]) {
  const max = Math.max(...data, 1)
  const points = data.map((v, i) => `${(i / (data.length - 1)) * 100},${30 - (v / max) * 25}`)
  return {
    line: `M${points.join(' L')}`,
    area: `M0,30 L${points.join(' L')} L100,30 Z`,
  }
}

const statCards = computed(() => [
  {
    label: '数据源', value: stats.datasource_total,
    desc: `${stats.datasource_active} 个可用`, color: '#2B5AED',
    sparkline: genSparkline([2,5,8,12,15,18,22,24]),
  },
  {
    label: '同步任务', value: stats.task_total,
    desc: `${stats.task_active} 个运行中`, color: '#00B42A',
    sparkline: genSparkline([1,3,5,8,10,12,14,15]),
  },
  {
    label: '调度工作流', value: stats.workflow_total,
    desc: `昨日执行 ${stats.yesterday_runs} 次`, color: '#FF7D00',
    sparkline: genSparkline(stats.workflow_trend.length ? stats.workflow_trend : [0,0,0,0,0,0,0]),
  },
  {
    label: '昨日执行', value: stats.yesterday_runs,
    desc: `成功 ${stats.yesterday_success} / 失败 ${stats.yesterday_failure}`,
    color: stats.yesterday_failure > 0 ? '#F53F3F' : '#00C9A7',
    sparkline: genSparkline(stats.workflow_trend.length ? stats.workflow_trend : [0,0,0,0,0,0,0]),
  },
])

const quickActions = [
  { title: '数据源管理', path: '/datasources', bg: 'rgba(43,90,237,0.08)', color: '#2B5AED', icon: IconLink },
  { title: '新建同步任务', path: '/sync-tasks', bg: 'rgba(0,180,42,0.08)', color: '#00B42A', icon: IconSync },
  { title: '调度中心', path: '/scheduler', bg: 'rgba(255,125,0,0.08)', color: '#FF7D00', icon: IconCalendar },
  { title: '数据资产', path: '/assets', bg: 'rgba(0,201,167,0.08)', color: '#00C9A7', icon: IconApps },
]

const notices = [
  { text: '数据中台 MVP v1.0 部署完成', time: '今天', color: '#2B5AED' },
  { text: 'DolphinScheduler 调度服务已就绪', time: '今天', color: '#00B42A' },
  { text: 'OpenMetadata 数据治理服务已就绪', time: '今天', color: '#00B42A' },
  { text: '请配置数据源后创建同步任务', time: '今天', color: '#FF7D00' },
]

onMounted(async () => {
  setInterval(() => { currentTime.value = new Date().toLocaleString('zh-CN') }, 1000)
  try {
    const res: any = await getDashboardStats()
    Object.assign(stats, res)
  } catch {}
})
</script>

<style scoped>
.dashboard { max-width: 1200px; animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* 欢迎横幅 */
.welcome-banner {
  background: #FFFFFF;
  border: 1px solid #E5E8ED;
  border-radius: 10px;
  padding: 24px 28px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.welcome-left { display: flex; align-items: stretch; gap: 16px; }
.welcome-accent {
  width: 4px;
  border-radius: 2px;
  background: linear-gradient(180deg, #2B5AED, #00C9A7);
  flex-shrink: 0;
}
.welcome-title { margin: 0 0 4px; font-size: 20px; font-weight: 600; color: #1D2129; }
.welcome-desc { margin: 0; font-size: 13px; color: #86909C; }
.welcome-time { font-size: 13px; color: #86909C; font-family: 'JetBrains Mono', monospace; }

/* 统计卡片 */
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.stat-card {
  padding: 0;
  position: relative;
  overflow: hidden;
  animation: slideUp 0.3s ease-out backwards;
  display: flex;
}
@keyframes slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.stat-color-bar { width: 4px; flex-shrink: 0; border-radius: 10px 0 0 10px; }
.stat-body { padding: 20px; flex: 1; min-width: 0; }
.stat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.stat-label { font-size: 13px; color: #86909C; }
.stat-value { font-size: 28px; font-weight: 700; font-family: 'DM Sans', 'Inter', sans-serif; line-height: 1.2; }
.stat-desc { font-size: 12px; color: #86909C; margin-top: 4px; }
.stat-sparkline { position: absolute; bottom: 0; left: 4px; right: 0; height: 30px; opacity: 0.8; }
.stat-sparkline svg { width: 100%; height: 100%; }

/* 昨日调度概览 */
.overview-section { padding: 20px; margin-bottom: 20px; }
.overview-grid { display: flex; gap: 40px; align-items: center; }
.overview-chart { flex-shrink: 0; }
.donut-wrap { position: relative; width: 120px; height: 120px; }
.donut-svg { width: 100%; height: 100%; }
.donut-center {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.donut-number { font-size: 24px; font-weight: 700; color: #1D2129; }
.donut-label { font-size: 11px; color: #86909C; }
.overview-details { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.detail-row { display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot.success { background: #00B42A; }
.dot.failure { background: #F53F3F; }
.dot.pending { background: #FF7D00; }
.detail-label { font-size: 13px; color: #4E5969; min-width: 48px; }
.detail-value { font-size: 15px; font-weight: 600; color: #1D2129; min-width: 32px; }
.detail-pct { font-size: 12px; color: #86909C; }
.overview-alert { flex: 1; }
.alert-bar {
  padding: 10px 16px; border-radius: 8px; font-size: 13px; font-weight: 500;
  display: flex; justify-content: space-between; align-items: center;
}
.alert-bar.failure { background: #FFF2F0; color: #F53F3F; cursor: pointer; }
.alert-bar.failure:hover { background: #FFE6E2; }
.alert-bar.success { background: #E8FFF3; color: #00B42A; }
.alert-bar.empty { background: #F7F8FA; color: #86909C; }
.alert-link { font-size: 12px; text-decoration: underline; }

/* 内容网格 */
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.section-title { margin: 0 0 16px; font-size: 15px; font-weight: 600; color: #1D2129; }

/* 快捷入口 */
.quick-section { padding: 20px; }
.quick-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.quick-item {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; border-radius: 8px;
  cursor: pointer; transition: background 0.15s;
}
.quick-item:hover { background: #F7F8FA; }
.quick-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
}
.quick-label { font-size: 13px; color: #1D2129; font-weight: 500; }

/* 公告 */
.notice-section { padding: 20px; }
.notice-row { display: flex; justify-content: space-between; align-items: center; }
.notice-text { color: #1D2129; font-size: 13px; }
.notice-time { color: #C9CDD4; font-size: 11px; flex-shrink: 0; margin-left: 12px; }

@media (max-width: 1200px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .content-grid { grid-template-columns: 1fr; }
}
</style>
