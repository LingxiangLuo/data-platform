<template>
  <div class="page">
    <div class="glass-card page-header">
      <div>
        <h3 class="page-title">数据资产</h3>
        <p class="page-desc">数据源库表元数据浏览 (Portal-native, 直连数据源)</p>
      </div>
      <a-space>
        <a-select v-model="dsId" :options="dsOptions" placeholder="选择数据源" style="width: 260px;" allow-clear @change="onDsChange" />
        <a-button @click="loadTables" :loading="tablesLoading">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </a-space>
    </div>

    <div v-if="!dsId" class="glass-card empty-card">
      <div class="empty-msg">请先在上方选择一个数据源</div>
    </div>

    <div v-else class="metadata-layout">
      <!-- 左侧:表列表 -->
      <div class="glass-card table-list-card">
        <div class="list-header">
          <span class="list-title">表清单 <span class="list-count">({{ filteredTables.length }})</span></span>
          <a-input v-model="tableFilter" placeholder="搜索表名" allow-clear style="width: 180px;">
            <template #prefix><icon-search /></template>
          </a-input>
        </div>
        <div class="table-list">
          <div v-if="tablesLoading" class="loading-state">
            <a-spin />
          </div>
          <div v-else-if="filteredTables.length === 0" class="empty-state">
            暂无表
          </div>
          <div
            v-for="t in filteredTables"
            :key="t.name"
            class="table-item"
            :class="{ active: selectedTable === t.name }"
            @click="selectTable(t.name)"
          >
            <div class="table-item-name">{{ t.name }}</div>
            <div class="table-item-meta">
              <a-tag size="small" color="arcoblue" v-if="t.type === 'BASE TABLE'">表</a-tag>
              <a-tag size="small" color="gray" v-else>{{ t.type }}</a-tag>
              <span class="mono">{{ t.rows }} 行</span>
              <span v-if="t.comment" class="comment">{{ t.comment }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧:表详情 -->
      <div class="glass-card table-detail-card">
        <div v-if="!selectedTable" class="placeholder">
          <icon-storage style="font-size: 32px; color: #C9CDD4;" />
          <p>点击左侧选择一张表查看详情</p>
        </div>
        <div v-else style="display: flex; flex-direction: column; flex: 1; overflow: hidden;">
          <div class="detail-header">
            <h4 class="detail-title">{{ selectedTable }}</h4>
            <a-tabs v-model:active-key="detailTab" type="line" size="small">
              <a-tab-pane key="columns" title="字段定义" />
              <a-tab-pane key="preview" title="数据预览" />
            </a-tabs>
          </div>

          <div class="detail-body">
            <!-- 字段定义 -->
          <div v-show="detailTab === 'columns'">
            <a-table
              :data="columns"
              :pagination="false"
              :loading="columnsLoading"
              :bordered="false"
              size="small"
              stripe
            >
              <template #columns>
                <a-table-column title="#" data-index="position" :width="60" />
                <a-table-column title="字段名" data-index="name" :width="180">
                  <template #cell="{ record }">
                    <span class="col-name">{{ record.name }}</span>
                    <a-tag v-if="record.primary_key" color="orange" size="small" style="margin-left:6px;">PK</a-tag>
                  </template>
                </a-table-column>
                <a-table-column title="类型" data-index="type" :width="160">
                  <template #cell="{ record }">
                    <span class="mono">{{ record.type }}</span>
                  </template>
                </a-table-column>
                <a-table-column title="可空" :width="70">
                  <template #cell="{ record }">
                    {{ record.nullable ? 'YES' : 'NO' }}
                  </template>
                </a-table-column>
                <a-table-column title="默认值" data-index="default" :width="120">
                  <template #cell="{ record }">
                    <span class="mono">{{ record.default ?? '—' }}</span>
                  </template>
                </a-table-column>
                <a-table-column title="备注" data-index="comment">
                  <template #cell="{ record }">
                    <span>{{ record.comment || '—' }}</span>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </div>

          <!-- 数据预览 -->
          <div v-show="detailTab === 'preview'">
            <div class="preview-toolbar">
              <a-button size="small" @click="loadPreview" :loading="previewLoading">
                <template #icon><icon-refresh /></template>
                刷新预览
              </a-button>
              <span class="preview-hint">前 10 行 (只读)</span>
            </div>
            <div v-if="previewLoading" class="loading-state"><a-spin /></div>
            <div v-else-if="!preview.columns?.length" class="empty-state">暂无数据</div>
            <div v-else class="preview-wrapper">
              <table class="preview-table mono">
                <thead>
                  <tr>
                    <th v-for="c in preview.columns" :key="c">{{ c }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in preview.rows" :key="i">
                    <td v-for="c in preview.columns" :key="c">{{ row[c] ?? '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconRefresh, IconSearch, IconStorage } from '@arco-design/web-vue/es/icon'
import { getDatasources, getMetadataTables, getMetadataColumns, getMetadataPreview } from '../api'

const dsOptions = ref<{ label: string; value: number }[]>([])
const dsId = ref<number | undefined>(undefined)
const tables = ref<any[]>([])
const tablesLoading = ref(false)
const tableFilter = ref('')

const selectedTable = ref<string | null>(null)
const detailTab = ref<'columns' | 'preview'>('columns')
const columns = ref<any[]>([])
const columnsLoading = ref(false)
const preview = ref<any>({ columns: [], rows: [] })
const previewLoading = ref(false)

const filteredTables = computed(() => {
  if (!tableFilter.value) return tables.value
  const kw = tableFilter.value.toLowerCase()
  return tables.value.filter(t => t.name.toLowerCase().includes(kw))
})

async function loadDatasources() {
  const res: any = await getDatasources({ page: 1, page_size: 100 })
  dsOptions.value = (res.items || [])
    .filter((d: any) => d.host && d.username)
    .map((d: any) => ({ label: `${d.name} (${d.type})`, value: d.id }))
  if (dsOptions.value.length && !dsId.value) {
    dsId.value = dsOptions.value[0].value
    await loadTables()
  }
}

async function loadTables() {
  if (!dsId.value) return
  tablesLoading.value = true
  selectedTable.value = null
  columns.value = []
  preview.value = { columns: [], rows: [] }
  try {
    const res: any = await getMetadataTables(dsId.value)
    tables.value = res.tables || []
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '读取表清单失败')
    tables.value = []
  }
  tablesLoading.value = false
}

function onDsChange() {
  loadTables()
}

async function selectTable(name: string) {
  selectedTable.value = name
  detailTab.value = 'columns'
  preview.value = { columns: [], rows: [] }
  columnsLoading.value = true
  try {
    const res: any = await getMetadataColumns(dsId.value!, name)
    columns.value = res.columns || []
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '读取字段失败')
    columns.value = []
  }
  columnsLoading.value = false
}

async function loadPreview() {
  if (!dsId.value || !selectedTable.value) return
  previewLoading.value = true
  try {
    const res: any = await getMetadataPreview(dsId.value, selectedTable.value, 10)
    preview.value = { columns: res.columns || [], rows: res.rows || [] }
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '数据预览失败')
    preview.value = { columns: [], rows: [] }
  }
  previewLoading.value = false
}

// 切换到预览 tab 时自动加载
import { watch } from 'vue'
watch(detailTab, (v) => { if (v === 'preview' && selectedTable.value && !preview.value.columns?.length) loadPreview() })

onMounted(loadDatasources)
</script>

<style scoped>
.page { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.page-header { padding: 20px 24px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 18px; font-weight: 600; color: #1D2129; }
.page-desc { margin: 4px 0 0; font-size: 13px; color: #86909C; }

.empty-card { padding: 60px 24px; text-align: center; }
.empty-msg { color: #86909C; font-size: 14px; }

.metadata-layout { display: grid; grid-template-columns: 360px 1fr; gap: 16px; }

.table-list-card { padding: 0; display: flex; flex-direction: column; max-height: calc(100vh - 200px); }
.list-header { padding: 14px 16px; border-bottom: 1px solid #F2F3F5; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.list-title { font-size: 14px; font-weight: 600; color: #1D2129; }
.list-count { color: #86909C; font-weight: 400; font-size: 12px; }
.table-list { flex: 1; overflow-y: auto; }
.table-item { padding: 10px 16px; border-bottom: 1px solid #F7F8FA; cursor: pointer; transition: background 0.15s; }
.table-item:hover { background: #F7F8FA; }
.table-item.active { background: #EFF4FF; border-left: 3px solid #2B5AED; padding-left: 13px; }
.table-item-name { font-size: 13px; font-weight: 500; color: #1D2129; margin-bottom: 4px; }
.table-item-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #86909C; }
.table-item-meta .comment { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 130px; }

.table-detail-card { padding: 0; min-height: 400px; max-height: calc(100vh - 200px); display: flex; flex-direction: column; overflow: hidden; }
.detail-body { flex: 1; overflow-y: auto; }
.placeholder { text-align: center; padding: 60px 0; color: #86909C; }
.placeholder p { margin-top: 8px; font-size: 13px; }
.detail-header { padding: 16px 20px 0; border-bottom: 1px solid #F2F3F5; }
.detail-title { margin: 0 0 8px; font-size: 16px; font-weight: 600; color: #1D2129; font-family: 'JetBrains Mono', monospace; }
.col-name { font-family: 'JetBrains Mono', monospace; color: #1D2129; }

.preview-toolbar { padding: 14px 20px 8px; display: flex; align-items: center; gap: 12px; }
.preview-hint { color: #86909C; font-size: 12px; }
.preview-wrapper { overflow-x: auto; padding: 0 20px 20px; }
.preview-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.preview-table th { padding: 8px 12px; text-align: left; background: #F7F8FA; border-bottom: 1px solid #E5E6EB; font-weight: 600; color: #4E5969; white-space: nowrap; }
.preview-table td { padding: 8px 12px; border-bottom: 1px solid #F2F3F5; color: #1D2129; white-space: nowrap; max-width: 240px; overflow: hidden; text-overflow: ellipsis; }
.preview-table tr:hover td { background: #F7F8FA; }

.loading-state, .empty-state { padding: 40px 0; text-align: center; color: #86909C; }
.mono { font-family: 'JetBrains Mono', 'Menlo', monospace; }
</style>
