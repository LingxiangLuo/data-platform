<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getScheduledWorkflows, scheduleWorkflowOnline, scheduleWorkflowOffline } from '../api'

interface ScheduledItem {
  id: number; name: string; cron_expression: string; schedule_status: string
  status: string; next_fire_time: string | null; ds_process_code: number | null
}

const items = ref<ScheduledItem[]>([])
const loading = ref(false)

onMounted(() => loadData())

async function loadData() {
  loading.value = true
  try {
    const res: any = await getScheduledWorkflows()
    items.value = res.items || []
  } catch { items.value = [] }
  finally { loading.value = false }
}

async function toggleSchedule(item: ScheduledItem) {
  try {
    if (item.schedule_status === 'ONLINE') {
      await scheduleWorkflowOffline(item.id)
      item.schedule_status = 'OFFLINE'
      Message.success('调度已关闭')
    } else {
      await scheduleWorkflowOnline(item.id)
      item.schedule_status = 'ONLINE'
      Message.success('调度已开启')
    }
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '操作失败')
  }
}

function statusColor(s: string): string {
  const map: Record<string, string> = { draft: '#86909c', tested: '#ff7d00', online: '#00b42a', offline: '#f53f3f' }
  return map[s] || '#86909c'
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h3 class="page-title">调度任务</h3>
        <p class="page-desc">管理所有配置了 CRON 定时调度的工作流</p>
      </div>
      <a-button @click="loadData">刷新</a-button>
    </div>

    <a-table :data="items" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="工作流名称" data-index="name" />
        <a-table-column title="CRON 表达式" data-index="cron_expression">
          <template #cell="{ record }">
            <code style="font-size: 12px; background: #f2f3f5; padding: 2px 6px; border-radius: 3px;">{{ record.cron_expression }}</code>
          </template>
        </a-table-column>
        <a-table-column title="下次执行时间" data-index="next_fire_time">
          <template #cell="{ record }">
            {{ record.next_fire_time || '-' }}
          </template>
        </a-table-column>
        <a-table-column title="工作流状态" data-index="status">
          <template #cell="{ record }">
            <span :style="{ color: statusColor(record.status) }">{{ record.status }}</span>
          </template>
        </a-table-column>
        <a-table-column title="调度开关">
          <template #cell="{ record }">
            <a-switch
              :model-value="record.schedule_status === 'ONLINE'"
              @change="toggleSchedule(record)"
              :disabled="record.status !== 'online'"
            />
          </template>
        </a-table-column>
      </template>
    </a-table>
  </div>
</template>

<style scoped>
.page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-title { margin: 0 0 4px; font-size: 18px; font-weight: 600; }
.page-desc { margin: 0; color: #86909c; font-size: 13px; }
</style>
