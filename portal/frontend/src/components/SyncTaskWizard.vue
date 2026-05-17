<template>
  <a-modal
    :visible="visible"
    @update:visible="(v: boolean) => emit('update:visible', v)"
    :title="editingId ? '编辑同步任务' : '新建同步任务'"
    :width="1100"
    :footer="false"
    :mask-closable="false"
    unmount-on-close
  >
    <div class="wizard-wrap">
      <a-steps :current="step" small change-on-click="false" type="navigation" class="wizard-steps">
        <a-step description="数据源 + 表">选择源表</a-step>
        <a-step description="数据源 + 表">选择目标表</a-step>
        <a-step description="同名映射 / 手动连线">字段映射</a-step>
        <a-step description="周期 + DataX 预览">配置 & 保存</a-step>
      </a-steps>

      <!-- Step 1: 源表 -->
      <div v-show="step === 0" class="wizard-step">
        <a-form :model="form" layout="vertical">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="源数据源" required>
                <a-select
                  v-model="form.source_id"
                  placeholder="选择源数据源"
                  @change="onSourceDsChange"
                  allow-search
                >
                  <a-option v-for="d in dsOptions" :key="d.id" :value="d.id" :label="`${d.name} (${d.type})`">
                    {{ d.name }} <span style="color:#86909C;font-size:12px">— {{ d.type }}@{{ d.host }}</span>
                  </a-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="源表" required>
                <a-select
                  v-model="form.source_table"
                  placeholder="先选择数据源"
                  :loading="srcTablesLoading"
                  :disabled="!form.source_id"
                  allow-search
                  @change="onSourceTableChange"
                >
                  <a-option v-for="t in srcTables" :key="t" :value="t">{{ t }}</a-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </a-form>
        <a-divider />
        <div class="step-hint">
          <icon-info-circle /> 选择源表后将自动读取字段结构，下一步用于映射目标表。
        </div>
        <div v-if="srcColumns.length > 0" class="cols-preview">
          <div class="cols-title">源字段（{{ srcColumns.length }} 列）</div>
          <a-table :data="srcColumns" :pagination="false" size="small" :scroll="{ y: 260 }">
            <template #columns>
              <a-table-column title="字段名" data-index="name" :width="200" />
              <a-table-column title="类型" data-index="type" :width="160" />
              <a-table-column title="注释" data-index="comment" />
            </template>
          </a-table>
        </div>
      </div>

      <!-- Step 2: 目标表 -->
      <div v-show="step === 1" class="wizard-step">
        <a-form :model="form" layout="vertical">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="目标数据源" required>
                <a-select v-model="form.target_id" @change="onTargetDsChange" allow-search>
                  <a-option v-for="d in dsOptions" :key="d.id" :value="d.id" :label="`${d.name} (${d.type})`">
                    {{ d.name }} <span style="color:#86909C;font-size:12px">— {{ d.type }}@{{ d.host }}</span>
                  </a-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="目标表" required>
                <a-select
                  v-model="form.target_table"
                  :loading="dstTablesLoading"
                  :disabled="!form.target_id"
                  allow-search
                  allow-create
                  @change="onTargetTableChange"
                  placeholder="选择已有表 或 输入新表名"
                >
                  <a-option v-for="t in dstTables" :key="t" :value="t">{{ t }}</a-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </a-form>
        <a-divider />
        <div v-if="dstColumns.length > 0" class="cols-preview">
          <div class="cols-title">目标字段（{{ dstColumns.length }} 列）</div>
          <a-table :data="dstColumns" :pagination="false" size="small" :scroll="{ y: 260 }">
            <template #columns>
              <a-table-column title="字段名" data-index="name" :width="200" />
              <a-table-column title="类型" data-index="type" :width="160" />
              <a-table-column title="注释" data-index="comment" />
            </template>
          </a-table>
        </div>
        <a-alert v-else-if="form.target_table" type="warning" style="margin-top:8px">
          目标表 {{ form.target_table }} 在元数据中不存在，下一步将使用源表结构作为目标字段。
        </a-alert>
      </div>

      <!-- Step 3: 字段映射 -->
      <div v-show="step === 2" class="wizard-step">
        <FieldMappingCanvas
          :source-columns="srcColumns"
          :target-columns="effectiveDstColumns"
          v-model="form.field_mapping"
        />
      </div>

      <!-- Step 4: 配置 + 预览 -->
      <div v-show="step === 3" class="wizard-step">
        <a-row :gutter="20">
          <a-col :span="10">
            <a-form :model="form" layout="vertical">
              <a-form-item label="任务名称" required>
                <a-input v-model="form.name" placeholder="例如 dim_brand → dwd_brand" />
              </a-form-item>
              <a-form-item label="所属项目">
                <a-select v-model="form.project_id" placeholder="不选 = 未分组" allow-clear>
                  <a-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</a-option>
                </a-select>
              </a-form-item>
              <a-form-item label="同步方式">
                <a-radio-group v-model="form.sync_type" type="button">
                  <a-radio value="full">全量</a-radio>
                  <a-radio value="increment">增量</a-radio>
                </a-radio-group>
              </a-form-item>
              <a-form-item v-if="form.sync_type === 'increment'" label="增量字段">
                <a-select v-model="form.increment_column" placeholder="选择增量列（如 update_time）">
                  <a-option v-for="c in srcColumns" :key="c.name" :value="c.name">
                    {{ c.name }} <span style="color:#86909C">— {{ c.type }}</span>
                  </a-option>
                </a-select>
              </a-form-item>
            </a-form>
          </a-col>
          <a-col :span="14">
            <div class="preview-wrap">
              <div class="preview-header">
                <icon-code /> DataX 配置预览
                <a-button size="mini" type="text" @click="refreshPreview" :loading="previewLoading">
                  <template #icon><icon-refresh /></template>刷新
                </a-button>
              </div>
              <pre class="preview-body">{{ previewText }}</pre>
            </div>
          </a-col>
        </a-row>
      </div>

      <a-divider style="margin: 16px 0 12px;" />
      <div class="wizard-footer">
        <a-button @click="emit('update:visible', false)">取消</a-button>
        <a-space>
          <a-button v-if="step > 0" @click="step--">上一步</a-button>
          <a-button v-if="step < 3" type="primary" @click="nextStep" :loading="stepLoading">下一步</a-button>
          <template v-if="step === 3">
            <a-button type="outline" @click="save" :loading="saving">
              {{ editingId ? '保存修改' : '仅保存' }}
            </a-button>
            <a-button v-if="!editingId" type="primary" @click="saveAndPublishAsWorkflow" :loading="publishing">
              发布为工作流
            </a-button>
          </template>
        </a-space>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconInfoCircle, IconCode, IconRefresh } from '@arco-design/web-vue/es/icon'
import FieldMappingCanvas from './FieldMappingCanvas.vue'
import {
  getDatasources, getMetadataTables, getMetadataColumns,
  createSyncTask, updateSyncTask, getSyncTask,
  previewSyncTaskUnsaved, publishSyncTaskAsWorkflow, createComponent, updateComponent, getComponents,
} from '../api'

const props = defineProps<{
  visible: boolean
  editingId?: number | null
  defaultProjectId?: number | null
  projects: any[]
}>()
const emit = defineEmits<{
  'update:visible': [v: boolean]
  'saved': []
}>()

const step = ref(0)
const stepLoading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const previewLoading = ref(false)

const dsOptions = ref<any[]>([])
const srcTables = ref<string[]>([])
const dstTables = ref<string[]>([])
const srcTablesLoading = ref(false)
const dstTablesLoading = ref(false)
const srcColumns = ref<any[]>([])
const dstColumns = ref<any[]>([])

const form = reactive<any>({
  name: '',
  project_id: null,
  source_id: null,
  target_id: null,
  source_table: '',
  target_table: '',
  sync_type: 'full',
  increment_column: null,
  field_mapping: [],
})

const previewText = ref('— 请先完成字段映射，进入此步会自动渲染 —')

// 目标字段：若元数据没找到，用源字段当占位
const effectiveDstColumns = computed(() => {
  if (dstColumns.value.length > 0) return dstColumns.value
  return srcColumns.value.map((c: any) => ({ name: c.name, type: c.type, comment: c.comment }))
})

async function loadDataSources() {
  const res: any = await getDatasources({ page_size: 200 })
  dsOptions.value = res.items || res.data || res || []
}

async function loadSrcTables() {
  if (!form.source_id) { srcTables.value = []; return }
  srcTablesLoading.value = true
  try {
    const res: any = await getMetadataTables(form.source_id)
    srcTables.value = (res.tables || res.items || res || []).map((t: any) => t.name || t)
  } catch { srcTables.value = [] }
  srcTablesLoading.value = false
}

async function loadSrcColumns() {
  if (!form.source_id || !form.source_table) { srcColumns.value = []; return }
  try {
    const res: any = await getMetadataColumns(form.source_id, form.source_table)
    srcColumns.value = (res.columns || res.items || res || []).map((c: any) => ({
      name: c.name || c.column_name,
      type: c.type || c.data_type || '',
      comment: c.comment || c.column_comment || '',
    }))
  } catch { srcColumns.value = [] }
}

async function loadDstTables() {
  if (!form.target_id) { dstTables.value = []; return }
  dstTablesLoading.value = true
  try {
    const res: any = await getMetadataTables(form.target_id)
    dstTables.value = (res.tables || res.items || res || []).map((t: any) => t.name || t)
  } catch { dstTables.value = [] }
  dstTablesLoading.value = false
}

async function loadDstColumns() {
  if (!form.target_id || !form.target_table) { dstColumns.value = []; return }
  try {
    const res: any = await getMetadataColumns(form.target_id, form.target_table)
    dstColumns.value = (res.columns || res.items || res || []).map((c: any) => ({
      name: c.name || c.column_name,
      type: c.type || c.data_type || '',
      comment: c.comment || c.column_comment || '',
    }))
  } catch { dstColumns.value = [] }
}

function onSourceDsChange() {
  form.source_table = ''
  srcColumns.value = []
  loadSrcTables()
}
function onSourceTableChange() { loadSrcColumns() }
function onTargetDsChange() {
  form.target_table = ''
  dstColumns.value = []
  loadDstTables()
}
function onTargetTableChange() { loadDstColumns() }

async function nextStep() {
  if (step.value === 0) {
    if (!form.source_id || !form.source_table) { Message.warning('请先选择源数据源和表'); return }
  } else if (step.value === 1) {
    if (!form.target_id || !form.target_table) { Message.warning('请选择目标数据源和表'); return }
  } else if (step.value === 2) {
    if (!form.field_mapping || form.field_mapping.length === 0) {
      Message.warning('至少需要一条字段映射')
      return
    }
  }
  step.value++
  if (step.value === 3) {
    await refreshPreview()
    if (!form.name && form.source_table && form.target_table) {
      form.name = `${form.source_table} → ${form.target_table}`
    }
  }
}

async function refreshPreview() {
  if (!form.field_mapping?.length) {
    previewText.value = '— 字段映射为空 —'
    return
  }
  previewLoading.value = true
  try {
    const res: any = await previewSyncTaskUnsaved({
      source_id: form.source_id,
      target_id: form.target_id,
      source_table: form.source_table,
      target_table: form.target_table,
      sync_type: form.sync_type,
      increment_column: form.increment_column,
      field_mapping: form.field_mapping,
    })
    previewText.value = JSON.stringify(res.datax || res, null, 2)
  } catch (e: any) {
    previewText.value = `预览失败：${e?.message || e}`
  } finally {
    previewLoading.value = false
  }
}

async function save() {
  if (!form.name) { Message.warning('请填写任务名称'); return }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      project_id: form.project_id,
      source_id: form.source_id,
      target_id: form.target_id,
      source_table: form.source_table,
      target_table: form.target_table,
      sync_type: form.sync_type,
      increment_column: form.increment_column,
      field_mapping: form.field_mapping,
    }
    if (props.editingId) {
      await updateSyncTask(props.editingId, payload)
      // 同步更新关联 Component 的 config_json（保持 source_table/target_table 显示一致）
      try {
        const res: any = await getComponents({ type: 'datax', page_size: 500 })
        const comps: any[] = res?.items || res?.data || res || []
        const comp = comps.find((c: any) => c.config_json?.sync_task_id === props.editingId)
        if (comp) {
          await updateComponent(comp.id, {
            name: form.name,
            config_json: {
              ...comp.config_json,
              source_table: form.source_table,
              target_table: form.target_table,
            },
          })
        }
      } catch {}
      Message.success('修改成功')
    } else {
      const task: any = await createSyncTask(payload)
      // 同时创建 datax 类型的 Component（草稿状态），使其出现在组件树
      await createComponent({
        name: form.name,
        type: 'datax',
        description: `DataX 同步：${form.source_table} → ${form.target_table}`,
        config_json: {
          sync_task_id: task.id,
          source_table: form.source_table,
          target_table: form.target_table,
        },
      })
      Message.success('创建成功')
    }
    emit('saved')
    emit('update:visible', false)
  } catch (e: any) {
    Message.error(`保存失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    saving.value = false
  }
}

async function saveAndPublishAsWorkflow() {
  if (!form.name) { Message.warning('请填写任务名称'); return }
  publishing.value = true
  try {
    let taskId: number
    const payload = {
      name: form.name,
      project_id: form.project_id,
      source_id: form.source_id,
      target_id: form.target_id,
      source_table: form.source_table,
      target_table: form.target_table,
      sync_type: form.sync_type,
      increment_column: form.increment_column,
      field_mapping: form.field_mapping,
    }
    if (props.editingId) {
      await updateSyncTask(props.editingId, payload)
      taskId = props.editingId
    } else {
      const res: any = await createSyncTask(payload)
      taskId = res.id
    }
    const wf: any = await publishSyncTaskAsWorkflow(taskId)
    Message.success(`已发布为工作流 #${wf.workflow_id}，DS 流程码：${wf.ds_process_code}`)
    emit('saved')
    emit('update:visible', false)
  } catch (e: any) {
    Message.error(`发布失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    publishing.value = false
  }
}

function resetForm() {
  step.value = 0
  Object.assign(form, {
    name: '', project_id: props.defaultProjectId || null,
    source_id: null, target_id: null,
    source_table: '', target_table: '',
    sync_type: 'full', increment_column: null,
    field_mapping: [],
  })
  srcTables.value = []; dstTables.value = []
  srcColumns.value = []; dstColumns.value = []
  previewText.value = '— 请先完成字段映射 —'
}

async function loadForEdit() {
  if (!props.editingId) return
  const t: any = await getSyncTask(props.editingId)
  form.name = t.name
  form.project_id = t.project_id
  form.source_id = t.source_id
  form.target_id = t.target_id
  form.source_table = t.source_table
  form.target_table = t.target_table
  form.sync_type = t.sync_type
  form.increment_column = t.increment_column
  form.field_mapping = t.field_mapping || []
  await Promise.all([loadSrcTables(), loadDstTables()])
  await Promise.all([loadSrcColumns(), loadDstColumns()])
}

watch(() => props.visible, async (v) => {
  if (!v) return
  resetForm()
  await loadDataSources()
  if (props.editingId) await loadForEdit()
})
</script>

<style scoped>
.wizard-wrap { padding: 0 4px; }
.wizard-steps { margin-bottom: 24px; }
.wizard-step { min-height: 520px; padding: 8px 4px; }
.step-hint {
  color: #86909C;
  font-size: 13px;
  padding: 8px 12px;
  background: #F7F8FA;
  border-radius: 4px;
}
.cols-preview { margin-top: 16px; }
.cols-title { font-weight: 600; margin-bottom: 8px; color: #1D2129; }
.preview-wrap {
  border: 1px solid #E5E6EB;
  border-radius: 6px;
  height: 480px;
  display: flex;
  flex-direction: column;
}
.preview-header {
  padding: 8px 12px;
  background: #F7F8FA;
  border-bottom: 1px solid #E5E6EB;
  font-weight: 600;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.preview-body {
  flex: 1;
  margin: 0;
  padding: 12px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  background: #1D2129;
  color: #C5C6C7;
  overflow: auto;
}
.wizard-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
