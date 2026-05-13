<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { getComponentFolders, getComponents } from '../../api'

interface TreeNode {
  nodeKey: string
  kind: 'folder' | 'component'
  id: number
  name: string
  depth: number
  folderType: string
  data?: any
}

const TYPE_GROUPS = [
  { type: 'sql',    label: 'SQL 查询',   color: '#2B5AED' },
  { type: 'python', label: 'Python 脚本', color: '#10b981' },
  { type: 'shell',  label: 'Shell 脚本',  color: '#f59e0b' },
  { type: 'datax',  label: 'DataX 同步',  color: '#8b5cf6' },
]

const TYPE_ABBR: Record<string, string> = { sql: 'S', python: 'P', shell: '$', datax: 'D' }

const components = ref<any[]>([])
const folders = ref<any[]>([])
const searchKw = ref('')

// 默认全部折叠
const grpCollapsed = reactive<Record<string, boolean>>({ sql: true, python: true, shell: true, datax: true })
const folderCollapsed = reactive<Record<number, boolean>>({})

onMounted(async () => {
  const [fRes, cRes]: any[] = await Promise.all([
    getComponentFolders(),
    getComponents({ status: 'online', page_size: 500 }),
  ])
  folders.value = Array.isArray(fRes) ? fRes : (fRes.items || [])
  components.value = (cRes.items || [])
})

function compCountByType(type: string) {
  return components.value.filter(c => c.type === type).length
}

function flatTree(type: string): TreeNode[] {
  const kw = searchKw.value.toLowerCase()
  const searching = !!kw
  const typeFolders = folders.value.filter(f => f.type === type)
  const typeComps = components.value.filter(c => {
    if (c.type !== type) return false
    if (kw && !c.name.toLowerCase().includes(kw)) return false
    return true
  })

  function folderHasMatch(folderId: number): boolean {
    if (typeComps.some(c => c.folder_id === folderId)) return true
    return typeFolders.filter(f => f.parent_id === folderId).some(sub => folderHasMatch(sub.id))
  }

  const result: TreeNode[] = []

  function traverse(parentId: number | null, depth: number) {
    const childFolders = typeFolders.filter(f => (f.parent_id ?? null) === parentId)
    for (const f of childFolders) {
      if (searching && !folderHasMatch(f.id)) continue
      result.push({ nodeKey: `f-${f.id}`, kind: 'folder', id: f.id, name: f.name, depth, folderType: type })
      if (searching || !folderCollapsed[f.id]) traverse(f.id, depth + 1)
    }
    const childComps = typeComps.filter(c => (c.folder_id ?? null) === parentId)
    for (const c of childComps) {
      result.push({ nodeKey: `c-${c.id}`, kind: 'component', id: c.id, name: c.name, depth, folderType: type, data: c })
    }
  }

  traverse(null, 0)
  return result
}

function toggleGrp(type: string) { grpCollapsed[type] = !grpCollapsed[type] }
function toggleFolder(id: number) { folderCollapsed[id] = !folderCollapsed[id] }

function onDragStart(event: DragEvent, comp: any) {
  event.dataTransfer!.setData('application/dag-component', JSON.stringify(comp))
  event.dataTransfer!.effectAllowed = 'move'
}

const typeColor = computed(() => Object.fromEntries(TYPE_GROUPS.map(g => [g.type, g.color])))
</script>

<template>
  <div class="dag-panel">
    <div class="dag-panel__header">
      <span class="dag-panel__title">组件库</span>
    </div>
    <div class="dag-panel__search">
      <input v-model="searchKw" placeholder="搜索组件..." class="dag-panel__input" />
    </div>

    <div class="dag-panel__tree">
      <template v-for="grp in TYPE_GROUPS" :key="grp.type">
        <!-- 类型组标题 -->
        <div class="grp-header" @click="toggleGrp(grp.type)">
          <span class="grp-caret" :class="{ collapsed: grpCollapsed[grp.type] }">▾</span>
          <span class="grp-dot" :style="{ background: grp.color }"></span>
          <span class="grp-label">{{ grp.label }}</span>
          <span class="grp-count">{{ compCountByType(grp.type) }}</span>
        </div>

        <!-- 展开后的树节点 -->
        <template v-if="searchKw || !grpCollapsed[grp.type]">
          <template v-for="node in flatTree(grp.type)" :key="node.nodeKey">

            <!-- 文件夹行 -->
            <div v-if="node.kind === 'folder'"
              class="tree-node folder-node"
              :style="{ paddingLeft: `${12 + node.depth * 14}px` }"
              @click="toggleFolder(node.id)">
              <span class="node-caret" :class="{ collapsed: folderCollapsed[node.id] }">▾</span>
              <span class="folder-icon">📁</span>
              <span class="node-name">{{ node.name }}</span>
            </div>

            <!-- 组件行 -->
            <div v-else
              class="tree-node comp-node"
              :style="{ paddingLeft: `${12 + node.depth * 14}px` }"
              draggable="true"
              @dragstart="onDragStart($event, node.data)">
              <span class="lang-badge" :style="{ background: typeColor[node.data.type] }">
                {{ TYPE_ABBR[node.data.type] || '?' }}
              </span>
              <span class="node-name">{{ node.name }}</span>
              <span class="drag-hint">⠿</span>
            </div>

          </template>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dag-panel { width: 240px; border-right: 1px solid #e5e7eb; display: flex; flex-direction: column; background: #fafbfc; overflow: hidden; }
.dag-panel__header { padding: 10px 14px 8px; border-bottom: 1px solid #e5e7eb; }
.dag-panel__title { font-size: 13px; font-weight: 600; color: #1d2129; }
.dag-panel__search { padding: 6px 10px; border-bottom: 1px solid #f2f3f5; }
.dag-panel__input { width: 100%; padding: 5px 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px; outline: none; background: #fff; }
.dag-panel__input:focus { border-color: #165dff; }
.dag-panel__tree { flex: 1; overflow-y: auto; padding: 4px 0; }

/* 类型组标题 */
.grp-header { display: flex; align-items: center; gap: 6px; padding: 5px 10px; cursor: pointer; font-size: 11px; font-weight: 600; color: #4e5969; user-select: none; transition: background 0.15s; }
.grp-header:hover { background: #f2f3f5; }
.grp-caret { font-size: 12px; color: #86909c; transition: transform 0.2s; display: inline-block; }
.grp-caret.collapsed { transform: rotate(-90deg); }
.grp-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.grp-label { flex: 1; }
.grp-count { font-size: 10px; background: #e5e6eb; color: #86909c; padding: 0 5px; border-radius: 8px; }

/* 树节点通用 */
.tree-node { display: flex; align-items: center; gap: 5px; height: 26px; font-size: 12px; cursor: pointer; transition: background 0.15s; padding-right: 6px; }
.tree-node:hover { background: #f2f3f5; }

/* 文件夹 */
.folder-node { color: #4e5969; font-weight: 500; }
.node-caret { font-size: 11px; color: #86909c; transition: transform 0.2s; display: inline-block; flex-shrink: 0; }
.node-caret.collapsed { transform: rotate(-90deg); }
.folder-icon { font-size: 12px; flex-shrink: 0; }

/* 组件 */
.comp-node { color: #1d2129; cursor: grab; }
.comp-node:hover { background: #eaf1ff; }
.comp-node:active { cursor: grabbing; }
.comp-node:hover .drag-hint { opacity: 1; }

.lang-badge { width: 16px; height: 16px; border-radius: 3px; color: #fff; font-size: 9px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.node-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.drag-hint { font-size: 12px; color: #c9cdd4; opacity: 0; transition: opacity 0.15s; flex-shrink: 0; }
</style>
