<template>
  <div class="page">
    <div class="glass-card page-header">
      <div>
        <h3 class="page-title">工作流管理</h3>
        <p class="page-desc">线性流水线 — 串联多个组件按顺序执行,可配置 CRON 调度</p>
      </div>
      <a-space>
        <a-input-search
          v-model="searchVal"
          placeholder="搜索工作流名"
          style="width: 200px;"
          @search="loadData"
          allow-clear
          @clear="loadData"
        />
        <a-button type="primary" @click="openCreate">
          <template #icon><icon-plus /></template>
          新建工作流
        </a-button>
      </a-space>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-tabs">
      <div class="tab-item" :class="{ active: statusFilter === '' }" @click="setStatus('')">全部 {{ total }}</div>
      <div class="tab-item" :class="{ active: statusFilter === 'draft' }" @click="setStatus('draft')">草稿</div>
      <div class="tab-item" :class="{ active: statusFilter === 'tested' }" @click="setStatus('tested')">已测试</div>
      <div class="tab-item online" :class="{ active: statusFilter === 'online' }" @click="setStatus('online')">已上线</div>
      <div class="tab-item" :class="{ active: statusFilter === 'offline' }" @click="setStatus('offline')">已下线</div>
    </div>

    <!-- 标签筛选 -->
    <div v-if="allTags.length" class="tag-filter-bar">
      <span class="tag-filter-label">标签：</span>
      <span class="tag-chip" :class="{ active: tagFilter === '' }" @click="setTag('')">全部</span>
      <span v-for="t in allTags" :key="t" class="tag-chip" :class="{ active: tagFilter === t }" @click="setTag(t)">{{ t }}</span>
    </div>

    <!-- 表格 -->
    <div class="glass-card table-card">
      <a-table :data="items" :loading="loading" :bordered="false" :pagination="false" stripe :scroll="{ x: 1300 }">
        <template #columns>
          <a-table-column title="工作流名" data-index="name" :width="180">
            <template #cell="{ record }">
              <span class="wf-name">{{ record.name }}</span>
              <span class="wf-version">v{{ record.version }}</span>
            </template>
          </a-table-column>
          <a-table-column title="步骤" :width="60">
            <template #cell="{ record }">
              <span class="mono">{{ (record.steps || []).length }}</span>
            </template>
          </a-table-column>
          <a-table-column title="状态" :width="80">
            <template #cell="{ record }">
              <a-tag :color="statusColor(record.status)" size="small">{{ statusLabel(record.status) }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="CRON" :width="120">
            <template #cell="{ record }">
              <span class="mono text-muted">{{ record.cron_expression || '—' }}</span>
            </template>
          </a-table-column>
          <a-table-column title="调度" :width="70">
            <template #cell="{ record }">
              <a-tag v-if="record.schedule_status === 'ONLINE'" color="green" size="small">运行中</a-tag>
              <a-tag v-else color="gray" size="small">停止</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="标签" :width="140">
            <template #cell="{ record }">
              <a-space :size="4" wrap>
                <a-tag v-for="t in (record.tags || [])" :key="t" size="small" color="arcoblue">{{ t }}</a-tag>
                <span v-if="!record.tags?.length" class="text-muted">—</span>
              </a-space>
            </template>
          </a-table-column>
          <a-table-column title="描述" data-index="description" :width="160" :ellipsis="true" :tooltip="true" />
          <a-table-column title="更新时间" :width="140">
            <template #cell="{ record }">
              <span class="mono text-muted text-nowrap">{{ formatTime(record.updated_at) }}</span>
            </template>
          </a-table-column>
          <a-table-column title="操作" :width="260" fixed="right">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="mini" @click="openEdit(record)" :disabled="!canEdit(record)">编辑</a-button>
                <a-button type="text" size="mini" status="success" @click="testWf(record)" :disabled="!canTest(record)">测试</a-button>
                <a-button v-if="record.status !== 'online'" type="text" size="mini" @click="publishWf(record)" :disabled="!canPublish(record)">发布</a-button>
                <a-button v-else type="text" size="mini" status="warning" @click="offlineWf(record)">下线</a-button>
                <a-dropdown>
                  <a-button type="text" size="mini">更多</a-button>
                  <template #content>
                    <a-doption @click="runWf(record)">运行</a-doption>
                    <a-doption @click="viewWf(record)">查看</a-doption>
                    <a-doption v-if="record.status === 'online' && record.schedule_status !== 'ONLINE'" @click="scheduleOn(record)">开启调度</a-doption>
                    <a-doption v-if="record.schedule_status === 'ONLINE'" @click="scheduleOff(record)">关闭调度</a-doption>
                    <a-doption :disabled="!canDelete(record)" @click="deleteWf(record)">删除</a-doption>
                  </template>
                </a-dropdown>
              </a-space>
            </template>
          </a-table-column>
        </template>
        <template #empty>
          <div class="empty-state">
            <p>暂无工作流</p>
            <p class="text-muted">点击「新建工作流」串联已发布的组件成一条流水线</p>
          </div>
        </template>
      </a-table>
      <div class="pagination-wrap" v-if="total > pageSize">
        <a-pagination v-model:current="page" :total="total" :page-size="pageSize" show-total @change="loadData" />
      </div>
    </div>

    <!-- 编辑器模态框 -->
    <a-modal
      v-model:visible="editorVisible"
      :title="editorTitle"
      :width="1000"
      :ok-text="readonlyMode ? '关闭' : '保存'"
      :hide-cancel="readonlyMode"
      @ok="handleSave"
      @cancel="editorVisible = false"
      :unmount-on-close="true"
    >
      <a-form :model="form" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="工作流名" required>
              <a-input v-model="form.name" placeholder="例如:daily_user_pipeline" :disabled="readonlyMode" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="CRON 表达式 (可选)">
              <a-input v-model="form.cron_expression" placeholder="例如:0 0 2 * * ? (DS 6 段 CRON)" :disabled="readonlyMode" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-input v-model="form.description" placeholder="可选" :disabled="readonlyMode" />
        </a-form-item>

        <!-- 线性步骤编辑器 -->
        <a-form-item label="执行步骤(按顺序)">
          <div class="steps-editor">
            <div v-if="form.steps.length === 0" class="steps-empty">
              <p class="text-muted">暂无步骤,点击下方按钮添加</p>
            </div>
            <div v-else class="step-list">
              <div v-for="(step, idx) in form.steps" :key="idx" class="step-row">
                <span class="step-order">{{ idx + 1 }}</span>
                <div class="step-info">
                  <span class="step-name">{{ step.component_name || ('组件 ' + step.component_id) }}</span>
                  <a-tag :color="typeColor(step.component_type)" size="small">{{ typeLabel(step.component_type) }}</a-tag>
                  <a-tag v-if="step.component_status !== 'online'" color="orangered" size="small">
                    {{ statusLabel(step.component_status) }}
                  </a-tag>
                </div>
                <div class="step-ops" v-if="!readonlyMode">
                  <a-button type="text" size="mini" :disabled="idx === 0" @click="moveStep(idx, -1)">
                    <icon-up />
                  </a-button>
                  <a-button type="text" size="mini" :disabled="idx === form.steps.length - 1" @click="moveStep(idx, 1)">
                    <icon-down />
                  </a-button>
                  <a-button type="text" size="mini" status="danger" @click="removeStep(idx)">
                    <icon-delete />
                  </a-button>
                </div>
              </div>
            </div>
            <div class="step-add" v-if="!readonlyMode">
              <a-select
                v-model="pendingCompId"
                placeholder="选择已上线组件添加为新步骤"
                style="flex: 1;"
                allow-search
                :loading="compsLoading"
              >
                <a-option v-for="c in onlineComps" :key="c.id" :value="c.id">
                  {{ c.name }} ({{ typeLabel(c.type) }})
                </a-option>
              </a-select>
              <a-button type="primary" @click="addStep" :disabled="!pendingCompId">
                <template #icon><icon-plus /></template>
                添加
              </a-button>
            </div>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconPlus, IconUp, IconDown, IconDelete,
} from '@arco-design/web-vue/es/icon'
import {
  getWorkflows, createWorkflow, updateWorkflow, deleteWorkflow,
  testWorkflow, publishWorkflow, offlineWorkflow, runWorkflow,
  scheduleWorkflowOnline, scheduleWorkflowOffline,
  getComponents,
} from '../api'

interface Step {
  component_id: number
  name?: string
  component_name?: string
  component_type?: string
  component_status?: string
}

interface Workflow {
  id: number
  name: string
  description?: string
  tags?: string[]
  steps: Step[]
  cron_expression?: string
  schedule_status: string
  status: string
  version: number
  ds_process_code?: number | null
  ds_schedule_id?: number | null
  created_at?: string
  updated_at?: string
}

const router = useRouter()
const loading = ref(false)
const items = ref<Workflow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchVal = ref('')
const statusFilter = ref('')
const tagFilter = ref('')
const allTags = ref<string[]>([])

const editorVisible = ref(false)
const editorTitle = ref('新建工作流')
const isEditMode = ref(false)
const readonlyMode = ref(false)
const editingId = ref<number | null>(null)

const onlineComps = ref<any[]>([])
const compsLoading = ref(false)
const pendingCompId = ref<number | undefined>(undefined)

interface FormState {
  name: string
  description: string
  cron_expression: string
  steps: Step[]
}

const form = reactive<FormState>({
  name: '',
  description: '',
  cron_expression: '',
  steps: [],
})

// ===== 工具函数 =====
function typeColor(t?: string) {
  if (!t) return 'gray'
  return ({ sql: 'blue', python: 'green', shell: 'orange', datax: 'purple' } as any)[t] || 'gray'
}
function typeLabel(t?: string) {
  if (!t) return '—'
  return ({ sql: 'SQL', python: 'Python', shell: 'Shell', datax: 'DataX' } as any)[t] || t
}
function statusColor(s: string) {
  return ({ draft: 'gray', tested: 'cyan', online: 'green', offline: 'orange' } as any)[s] || 'gray'
}
function statusLabel(s?: string) {
  if (!s) return '未知'
  return ({ draft: '草稿', tested: '已测试', online: '已上线', offline: '已下线' } as any)[s] || s
}
function formatTime(t?: string) {
  if (!t) return '—'
  return t.replace('T', ' ').split('.')[0]
}

function canEdit(w: Workflow) { return w.status === 'draft' || w.status === 'tested' || w.status === 'offline' }
function canTest(w: Workflow) { return w.status === 'draft' || w.status === 'tested' }
function canPublish(w: Workflow) { return w.status === 'tested' }
function canDelete(w: Workflow) { return w.status === 'draft' || w.status === 'offline' }

function setStatus(s: string) { statusFilter.value = s; loadData() }
function setTag(t: string) { tagFilter.value = t; loadData() }

// ===== 数据加载 =====
async function loadData() {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (searchVal.value) params.keyword = searchVal.value
    if (statusFilter.value) params.status = statusFilter.value
    if (tagFilter.value) params.tag = tagFilter.value
    const res: any = await getWorkflows(params)
    items.value = res?.items || []
    total.value = res?.total || 0
    if (res?.all_tags) allTags.value = res.all_tags
  } catch {
    items.value = []
    total.value = 0
  }
  loading.value = false
}

async function loadOnlineComponents() {
  compsLoading.value = true
  try {
    // 只允许已上线的组件被添加为步骤
    const res: any = await getComponents({ page: 1, page_size: 200, status: 'online' })
    onlineComps.value = res?.items || []
  } catch {
    onlineComps.value = []
  }
  compsLoading.value = false
}

// ===== 表单 =====
function resetForm() {
  form.name = ''
  form.description = ''
  form.cron_expression = ''
  form.steps = []
  pendingCompId.value = undefined
}

function loadFormFromWf(w: Workflow) {
  form.name = w.name
  form.description = w.description || ''
  form.cron_expression = w.cron_expression || ''
  form.steps = (w.steps || []).map(s => ({ ...s }))
  pendingCompId.value = undefined
}

function buildPayload() {
  return {
    name: form.name,
    description: form.description || null,
    cron_expression: form.cron_expression || null,
    steps: form.steps.map(s => ({ component_id: s.component_id, name: s.name || null })),
  }
}

function addStep() {
  if (!pendingCompId.value) return
  const c = onlineComps.value.find(x => x.id === pendingCompId.value)
  if (!c) return
  form.steps.push({
    component_id: c.id,
    name: c.name,
    component_name: c.name,
    component_type: c.type,
    component_status: c.status,
  })
  pendingCompId.value = undefined
}

function removeStep(idx: number) {
  form.steps.splice(idx, 1)
}

function moveStep(idx: number, direction: number) {
  const newIdx = idx + direction
  if (newIdx < 0 || newIdx >= form.steps.length) return
  const tmp = form.steps[idx]
  form.steps[idx] = form.steps[newIdx]
  form.steps[newIdx] = tmp
}

// ===== 操作 =====
function openCreate() {
  router.push('/workflows/new/edit')
}

function openEdit(w: Workflow) {
  router.push(`/workflows/${w.id}/edit`)
}

function viewWf(w: Workflow) {
  loadFormFromWf(w)
  isEditMode.value = true
  readonlyMode.value = true
  editingId.value = w.id
  editorTitle.value = `查看 - ${w.name}`
  editorVisible.value = true
}

async function handleSave() {
  if (readonlyMode.value) {
    editorVisible.value = false
    return
  }
  if (!form.name.trim()) {
    Message.warning('请填写工作流名')
    return
  }
  if (form.steps.length === 0) {
    Message.warning('至少添加 1 个步骤')
    return
  }
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await updateWorkflow(editingId.value, payload)
      Message.success('已保存(状态回到 draft,需重新测试)')
    } else {
      await createWorkflow(payload)
      Message.success('已创建')
    }
    editorVisible.value = false
    loadData()
  } catch {}
}

function testWf(w: Workflow) {
  Modal.confirm({
    title: '测试工作流',
    content: `将检查所有组件状态并触发试运行,通过后状态转为已测试,确认?`,
    onOk: async () => {
      try {
        await testWorkflow(w.id)
        Message.success('测试通过')
        loadData()
      } catch {}
    },
  })
}

function publishWf(w: Workflow) {
  Modal.confirm({
    title: '发布工作流',
    content: `「${w.name}」将发布上线,确认?(Phase 4 仅切状态,Phase 5/6 同步 DS)`,
    onOk: async () => {
      try {
        await publishWorkflow(w.id)
        Message.success('已发布')
        loadData()
      } catch {}
    },
  })
}

function offlineWf(w: Workflow) {
  Modal.confirm({
    title: '下线工作流',
    content: `确认下线「${w.name}」?调度也会自动停止`,
    onOk: async () => {
      try {
        await offlineWorkflow(w.id)
        Message.success('已下线')
        loadData()
      } catch {}
    },
  })
}

function runWf(w: Workflow) {
  Modal.confirm({
    title: '手动运行',
    content: `立即运行「${w.name}」?`,
    onOk: async () => {
      try {
        await runWorkflow(w.id)
        Message.success('已触发运行')
      } catch {}
    },
  })
}

function scheduleOn(w: Workflow) {
  if (!w.cron_expression) {
    Message.warning('该工作流未配置 CRON,请先编辑设置')
    return
  }
  Modal.confirm({
    title: '开启调度',
    content: `按 CRON「${w.cron_expression}」开启自动调度?`,
    onOk: async () => {
      try {
        await scheduleWorkflowOnline(w.id)
        Message.success('调度已开启')
        loadData()
      } catch {}
    },
  })
}

function scheduleOff(w: Workflow) {
  Modal.confirm({
    title: '关闭调度',
    content: `关闭「${w.name}」的自动调度?`,
    onOk: async () => {
      try {
        await scheduleWorkflowOffline(w.id)
        Message.success('调度已关闭')
        loadData()
      } catch {}
    },
  })
}

function deleteWf(w: Workflow) {
  Modal.confirm({
    title: '删除工作流',
    content: `确认删除「${w.name}」?该操作不可恢复`,
    onOk: async () => {
      try {
        await deleteWorkflow(w.id)
        Message.success('已删除')
        loadData()
      } catch {}
    },
  })
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.page-header { padding: 20px 24px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 18px; font-weight: 600; color: #1D2129; }
.page-desc { margin: 4px 0 0; font-size: 13px; color: #86909C; }

.filter-tabs { display: flex; gap: 4px; margin-bottom: 8px; }
.tab-item {
  padding: 6px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;
  color: #4E5969; background: #F7F8FA; transition: all 0.15s;
}
.tab-item:hover { background: #EFF4FF; color: #2B5AED; }
.tab-item.active { background: #2B5AED; color: #FFFFFF; }
.tab-item.online.active { background: #00B42A; }
.tag-filter-bar { display: flex; align-items: center; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.tag-filter-label { font-size: 12px; color: #86909c; }
.tag-chip { padding: 3px 10px; border-radius: 10px; font-size: 12px; cursor: pointer; background: #f2f3f5; color: #4e5969; transition: all 0.15s; }
.tag-chip:hover { background: #e8f3ff; color: #165dff; }
.tag-chip.active { background: #165dff; color: #fff; }

.table-card { padding: 0; overflow: hidden; }
.wf-name { font-weight: 500; color: #1D2129; }
.wf-version {
  margin-left: 8px; font-size: 11px; color: #86909C;
  font-family: 'JetBrains Mono', monospace;
}

.mono { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.text-muted { color: #86909C; }
.text-nowrap { white-space: nowrap; }
.cell-ellipsis { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { padding: 40px 0; text-align: center; }
.pagination-wrap { padding: 16px 24px; display: flex; justify-content: flex-end; border-top: 1px solid #F2F3F5; }
:deep(.arco-table-th) { background: #FAFBFC !important; }

/* 步骤编辑器 */
.steps-editor {
  border: 1px dashed #E5E8ED;
  border-radius: 8px;
  padding: 12px;
  background: #FAFBFC;
}
.steps-empty {
  text-align: center;
  padding: 16px 0;
}
.step-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.step-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: #FFFFFF;
  border: 1px solid #E5E8ED;
  border-radius: 6px;
  transition: border-color 0.15s;
}
.step-row:hover { border-color: #2B5AED; }
.step-order {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  background: #2B5AED; color: #FFFFFF;
  border-radius: 50%;
  font-size: 13px; font-weight: 600;
  flex-shrink: 0;
}
.step-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-name { font-size: 14px; color: #1D2129; }
.step-ops {
  display: flex;
  gap: 2px;
}

.step-add {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
