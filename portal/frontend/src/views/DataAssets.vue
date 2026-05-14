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
              <a-tab-pane key="quality" title="数据质量" />
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
                <a-table-column title="字段名" data-index="name" :width="220">
                  <template #cell="{ record }">
                    <span class="col-name" :class="{ 'pk-highlight': record.primary_key }">{{ record.name }}</span>
                    <span class="field-badges">
                      <span v-if="record.primary_key" class="mini-badge badge-pk" title="主键">P</span>
                      <span v-if="!record.nullable" class="mini-badge badge-nn" title="非空">N</span>
                      <span v-if="record.auto_increment" class="mini-badge badge-auto" title="自增">A</span>
                      <span v-if="record.unique" class="mini-badge badge-uq" title="唯一">U</span>
                      <span v-if="record.index" class="mini-badge badge-idx" title="索引">I</span>
                    </span>
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
                    <th v-for="c in preview.columns" :key="c" :class="{ 'pk-header': getColumnMeta(c)?.primary_key }">
                      <span class="col-name" :class="{ 'pk-highlight': getColumnMeta(c)?.primary_key }">{{ c }}</span>
                      <span class="field-badges preview-badges">
                        <span v-if="getColumnMeta(c)?.primary_key" class="mini-badge badge-pk" title="主键">P</span>
                        <span v-if="getColumnMeta(c) && !getColumnMeta(c).nullable" class="mini-badge badge-nn" title="非空">N</span>
                        <span v-if="getColumnMeta(c)?.auto_increment" class="mini-badge badge-auto" title="自增">A</span>
                        <span v-if="getColumnMeta(c)?.unique" class="mini-badge badge-uq" title="唯一">U</span>
                        <span v-if="getColumnMeta(c)?.index" class="mini-badge badge-idx" title="索引">I</span>
                      </span>
                    </th>
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

          <!-- 数据质量 -->
          <div v-show="detailTab === 'quality'">
            <div v-if="qualityLoading" class="loading-state"><a-spin /></div>
            <div v-else-if="!quality.columns?.length" class="empty-state">暂无质量数据</div>
            <div v-else class="quality-panel">
              <!-- 概览卡片 -->
              <div class="quality-overview">
                <div class="q-card q-score">
                  <div class="q-val">{{ qualityScore }}</div>
                  <div class="q-label">质量总分</div>
                  <a-progress :percent="qualityScore" :stroke-width="6" size="small" :color="scoreColor" />
                </div>
                <div class="q-card">
                  <div class="q-val text-green">{{ quality.columns.filter((c: any) => c.score >= 90).length }}</div>
                  <div class="q-label">完整字段</div>
                </div>
                <div class="q-card">
                  <div class="q-val text-red">{{ quality.columns.filter((c: any) => c.score < 90).length }}</div>
                  <div class="q-label">问题字段</div>
                </div>
                <div class="q-card">
                  <div class="q-val">{{ quality.total_rows.toLocaleString() }}</div>
                  <div class="q-label">总行数</div>
                </div>
              </div>

              <!-- 字段质量表格 -->
              <a-table
                :data="quality.columns"
                :pagination="false"
                :bordered="false"
                size="small"
                stripe
              >
                <template #columns>
                  <a-table-column title="字段名" :width="220">
                    <template #cell="{ record }">
                      <span class="col-name" :class="{ 'pk-highlight': record.primary_key }">{{ record.name }}</span>
                      <span class="field-badges">
                        <span v-if="record.primary_key" class="mini-badge badge-pk" title="主键">P</span>
                        <span v-if="!record.nullable" class="mini-badge badge-nn" title="非空">N</span>
                        <span v-if="record.auto_increment" class="mini-badge badge-auto" title="自增">A</span>
                        <span v-if="record.unique" class="mini-badge badge-uq" title="唯一">U</span>
                        <span v-if="record.index" class="mini-badge badge-idx" title="索引">I</span>
                      </span>
                    </template>
                  </a-table-column>
                  <a-table-column title="类型" :width="120">
                    <template #cell="{ record }">
                      <span class="mono">{{ record.type }}</span>
                    </template>
                  </a-table-column>
                  <a-table-column title="空值率" :width="140">
                    <template #cell="{ record }">
                      <a-progress
                        :percent="Math.round(record.null_rate * 100)"
                        :stroke-width="4"
                        size="small"
                        :color="record.null_rate > 0.2 ? '#f53f3f' : record.null_rate > 0 ? '#ff7d00' : '#00b42a'"
                      />
                      <span class="rate-text">{{ (record.null_rate * 100).toFixed(1) }}%</span>
                    </template>
                  </a-table-column>
                  <a-table-column title="重复率" :width="100">
                    <template #cell="{ record }">
                      <span :class="{ 'text-red': record.duplicate_rate > 0.1 }">{{ (record.duplicate_rate * 100).toFixed(1) }}%</span>
                    </template>
                  </a-table-column>
                  <a-table-column title="统计信息" :width="200">
                    <template #cell="{ record }">
                      <span v-if="record.min != null" class="mini-stats">
                        min:{{ record.min }} max:{{ record.max }}<span v-if="record.avg"> avg:{{ record.avg }}</span>
                      </span>
                      <span v-else class="mini-stats muted">—</span>
                    </template>
                  </a-table-column>
                  <a-table-column title="评分" :width="80">
                    <template #cell="{ record }">
                      <span class="score-badge" :class="{ 'score-bad': record.score < 60, 'score-warn': record.score >= 60 && record.score < 90, 'score-good': record.score >= 90 }">
                        {{ record.score }}
                      </span>
                    </template>
                  </a-table-column>
                  <a-table-column title="问题" >
                    <template #cell="{ record }">
                      <span v-if="!record.issues?.length" class="muted">✓ 正常</span>
                      <span v-else class="issue-list">
                        <a-tag v-for="(issue, i) in record.issues" :key="i" color="#f53f3f" size="small">{{ issue }}</a-tag>
                      </span>
                    </template>
                  </a-table-column>
                </template>
              </a-table>

              <!-- 异常摘要 -->
              <div v-if="allIssues.length" class="quality-anomaly">
                <div class="anomaly-title">⚠ 异常摘要</div>
                <div class="anomaly-list">
                  <div v-for="(item, i) in allIssues" :key="i" class="anomaly-item">
                    <span class="anomaly-field">{{ item.field }}</span>
                    <span class="anomaly-issues">{{ item.issues.join('；') }}</span>
                  </div>
                </div>
              </div>
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
import { getDatasources, getMetadataTables, getMetadataColumns, getMetadataPreview, getMetadataQuality } from '../api'

const dsOptions = ref<{ label: string; value: number }[]>([])
const dsId = ref<number | undefined>(undefined)
const tables = ref<any[]>([])
const tablesLoading = ref(false)
const tableFilter = ref('')

const selectedTable = ref<string | null>(null)
const detailTab = ref<'columns' | 'preview' | 'quality'>('columns')
const columns = ref<any[]>([])
const columnsLoading = ref(false)
const preview = ref<any>({ columns: [], rows: [] })
const previewLoading = ref(false)
const quality = ref<any>({ total_rows: 0, columns: [] })
const qualityLoading = ref(false)

const filteredTables = computed(() => {
  if (!tableFilter.value) return tables.value
  const kw = tableFilter.value.toLowerCase()
  return tables.value.filter(t => t.name.toLowerCase().includes(kw))
})

function getColumnMeta(colName: string) {
  return columns.value.find((c: any) => c.name === colName)
}

const qualityScore = computed(() => {
  if (!quality.value.columns?.length) return 0
  const total = quality.value.columns.reduce((s: number, c: any) => s + c.score, 0)
  return Math.round(total / quality.value.columns.length)
})

const scoreColor = computed(() => {
  const s = qualityScore.value
  if (s >= 90) return '#00b42a'
  if (s >= 60) return '#ff7d00'
  return '#f53f3f'
})

const allIssues = computed(() => {
  return quality.value.columns
    ?.filter((c: any) => c.issues?.length)
    ?.map((c: any) => ({ field: c.name, issues: c.issues })) || []
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
  quality.value = { total_rows: 0, columns: [] }
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

async function loadQuality() {
  if (!dsId.value || !selectedTable.value) return
  qualityLoading.value = true
  try {
    const res: any = await getMetadataQuality(dsId.value, selectedTable.value)
    quality.value = {
      total_rows: res.total_rows || 0,
      columns: res.columns || [],
    }
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '数据质量分析失败')
    quality.value = { total_rows: 0, columns: [] }
  }
  qualityLoading.value = false
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
watch(detailTab, (v) => {
  if (v === 'preview' && selectedTable.value && !preview.value.columns?.length) loadPreview()
  if (v === 'quality' && selectedTable.value && !quality.value.columns?.length) loadQuality()
})

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

/* 字段角标 */
.field-badges { display: inline-flex; gap: 2px; margin-left: 4px; vertical-align: text-bottom; flex-wrap: nowrap; }
.mini-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  padding: 0 3px;
  height: 13px;
  line-height: 13px;
  border-radius: 2px;
  cursor: default;
}
.badge-pk { background: #FFF3E8; color: #D46B08; }
.badge-nn { background: #F5F5F5; color: #8C8C8C; }
.badge-auto { background: #E6F4FF; color: #0958D9; }
.badge-uq { background: #E8FFEA; color: #389E0D; }
.badge-idx { background: #F5F5F5; color: #BFBFBF; }
.pk-highlight { color: #D46B08; font-weight: 600; }
.pk-header { background: #FFF7E8 !important; }

/* 预览表格中的角标更小 */
.preview-badges { margin-left: 2px; gap: 1px; }
.preview-badges .mini-badge { font-size: 8px; padding: 0 2px; height: 11px; line-height: 11px; }

/* 数据质量 */
.quality-panel { padding: 0 0 16px; }
.quality-overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; padding: 16px 20px; border-bottom: 1px solid #F2F3F5; }
.q-card { background: #F7F8FA; border-radius: 8px; padding: 14px 16px; text-align: center; }
.q-val { font-size: 22px; font-weight: 700; color: #1D2129; line-height: 1.2; }
.q-label { font-size: 12px; color: #86909C; margin-top: 4px; }
.text-green { color: #00B42A; }
.text-red { color: #F53F3F; }

.rate-text { font-size: 11px; color: #86909C; margin-left: 6px; }
.mini-stats { font-size: 11px; color: #4E5969; font-family: 'JetBrains Mono', monospace; }
.mini-stats.muted { color: #C9CDD4; }

.score-badge { display: inline-block; min-width: 32px; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 700; text-align: center; }
.score-good { background: #E8FFEA; color: #00B42A; }
.score-warn { background: #FFF7E8; color: #FF7D00; }
.score-bad { background: #FFECE8; color: #F53F3F; }

.issue-list { display: flex; gap: 4px; flex-wrap: wrap; }
.issue-list .arco-tag { font-size: 10px; padding: 0 4px; height: 18px; line-height: 16px; }

.quality-anomaly { margin: 16px 20px 0; padding: 14px 16px; background: #FFF7E8; border-radius: 8px; border: 1px solid #FFDFA8; }
.anomaly-title { font-size: 13px; font-weight: 600; color: #FF7D00; margin-bottom: 8px; }
.anomaly-list { display: flex; flex-direction: column; gap: 6px; }
.anomaly-item { display: flex; gap: 8px; font-size: 12px; }
.anomaly-field { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #1D2129; min-width: 120px; }
.anomaly-issues { color: #4E5969; }
.muted { color: #C9CDD4; font-size: 12px; }
</style>
