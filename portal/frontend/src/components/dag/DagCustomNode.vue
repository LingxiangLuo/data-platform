<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps<{
  data: {
    label: string
    type: string
    skip: boolean
    status?: string
  }
}>()

const typeConfig = computed(() => {
  const map: Record<string, { color: string; icon: string }> = {
    sql: { color: '#3b82f6', icon: 'S' },
    python: { color: '#10b981', icon: 'P' },
    shell: { color: '#f59e0b', icon: '$' },
    datax: { color: '#8b5cf6', icon: 'D' },
  }
  return map[props.data.type] || { color: '#6b7280', icon: '?' }
})
</script>

<template>
  <div
    class="dag-node"
    :class="{ 'dag-node--skip': data.skip }"
    :style="{ borderColor: typeConfig.color }"
  >
    <Handle type="target" :position="Position.Top" />
    <div class="dag-node__header" :style="{ background: typeConfig.color }">
      <span class="dag-node__icon">{{ typeConfig.icon }}</span>
      <span class="dag-node__type">{{ data.type }}</span>
    </div>
    <div class="dag-node__body">
      <span class="dag-node__label">{{ data.label }}</span>
      <span v-if="data.skip" class="dag-node__skip-badge">SKIP</span>
    </div>
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.dag-node {
  min-width: 160px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  overflow: hidden;
  transition: all 0.2s;
}
.dag-node:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
.dag-node--skip { opacity: 0.5; }
.dag-node--skip .dag-node__label { text-decoration: line-through; }
.dag-node__header {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; color: #fff; font-size: 11px; font-weight: 600;
}
.dag-node__icon { font-family: monospace; font-size: 13px; }
.dag-node__body { padding: 8px 10px; font-size: 13px; display: flex; align-items: center; gap: 6px; }
.dag-node__label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dag-node__skip-badge {
  font-size: 10px; background: #ef4444; color: #fff;
  padding: 1px 4px; border-radius: 3px; font-weight: 600;
}
</style>
