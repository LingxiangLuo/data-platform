<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getComponents } from '../../api'

interface Comp {
  id: number; name: string; type: string; description?: string
}

const components = ref<Comp[]>([])
const searchKey = ref('')

onMounted(async () => {
  const res: any = await getComponents({ status: 'online', page_size: 200 })
  components.value = res.items || []
})

const grouped = computed(() => {
  const groups: Record<string, Comp[]> = { sql: [], python: [], shell: [], datax: [] }
  const filtered = components.value.filter(c =>
    !searchKey.value || c.name.toLowerCase().includes(searchKey.value.toLowerCase())
  )
  filtered.forEach(c => {
    if (groups[c.type]) groups[c.type].push(c)
  })
  return groups
})

const typeLabels: Record<string, string> = {
  sql: 'SQL', python: 'Python', shell: 'Shell', datax: 'DataX'
}
const typeColors: Record<string, string> = {
  sql: '#3b82f6', python: '#10b981', shell: '#f59e0b', datax: '#8b5cf6'
}

function onDragStart(event: DragEvent, comp: Comp) {
  event.dataTransfer!.setData('application/dag-component', JSON.stringify(comp))
  event.dataTransfer!.effectAllowed = 'move'
}
</script>

<template>
  <div class="dag-panel">
    <div class="dag-panel__header">
      <h3>组件库</h3>
    </div>
    <div class="dag-panel__search">
      <input v-model="searchKey" placeholder="搜索组件..." />
    </div>
    <div class="dag-panel__groups">
      <div v-for="(items, type) in grouped" :key="type" class="dag-panel__group">
        <div class="dag-panel__group-title" v-if="items.length">
          <span class="dag-panel__dot" :style="{ background: typeColors[type] }"></span>
          {{ typeLabels[type] }} ({{ items.length }})
        </div>
        <div
          v-for="comp in items" :key="comp.id"
          class="dag-panel__item"
          draggable="true"
          @dragstart="onDragStart($event, comp)"
        >
          <span class="dag-panel__item-name">{{ comp.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dag-panel { width: 240px; border-right: 1px solid #e5e7eb; display: flex; flex-direction: column; background: #fafbfc; }
.dag-panel__header { padding: 12px 16px; border-bottom: 1px solid #e5e7eb; }
.dag-panel__header h3 { margin: 0; font-size: 14px; font-weight: 600; }
.dag-panel__search { padding: 8px 12px; }
.dag-panel__search input { width: 100%; padding: 6px 10px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; outline: none; }
.dag-panel__search input:focus { border-color: #165dff; }
.dag-panel__groups { flex: 1; overflow-y: auto; padding: 0 12px 12px; }
.dag-panel__group { margin-bottom: 8px; }
.dag-panel__group-title { font-size: 12px; font-weight: 600; color: #666; padding: 6px 0; display: flex; align-items: center; gap: 6px; }
.dag-panel__dot { width: 8px; height: 8px; border-radius: 50%; }
.dag-panel__item { padding: 6px 10px; margin: 2px 0; border-radius: 4px; cursor: grab; font-size: 13px; background: #fff; border: 1px solid #e5e7eb; transition: all 0.15s; }
.dag-panel__item:hover { border-color: #165dff; background: #f0f5ff; }
.dag-panel__item:active { cursor: grabbing; }
.dag-panel__item-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }
</style>