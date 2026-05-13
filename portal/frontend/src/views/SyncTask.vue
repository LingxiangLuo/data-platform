<template>
  <div class="ide-layout">
    <!-- 左侧：项目 / 任务树 -->
    <div class="left-sider">
      <div class="sider-header">
        <span class="sider-title">同步任务</span>
        <a-button type="primary" size="mini" @click="newTask()">
          <template #icon><icon-plus /></template>
          新建
        </a-button>
      </div>
      <div class="sider-toolbar">
        <a-input
          v-model="searchKw"
          placeholder="搜索任务名"
          allow-clear
          size="small"
        >
          <template #prefix><icon-search /></template>
        </a-input>
      </div>
      <div class="tree-area">
        <div
          v-for="p in projects"
          :key="p.id"
          class="proj-group"
        >
          <div class="proj-row" @click="toggleProject(p.id)">
            <icon-down v-if="!collapsed[p.id]" class="caret" />
            <icon-right v-else class="caret" />
            <span class="proj-color-dot" :style="{ background: p.color }"></span>
            <span class="proj-name">{{ p.name }}</span>
            <a-tag v-if="p.is_default" size="small" color="gray" class="proj-tag">默认</a-tag>
            <span class="proj-count">{{ p.task_count }}</span>
            <a-dropdown v-if="!p.is_default" trigger="click" @click.stop>
              <a-button type="text" size="mini" class="proj-menu" @click.stop>
                <icon-more />
              </a-button>
              <template #content>
                <a-doption @click="showProjectModal(p)"><icon-edit /> 编辑项目</a-doption>
                <a-doption @click="handleDeleteProject(p)" style="color:#F53F3F"><icon-delete /> 删除项目</a-doption>
              </template>
            </a-dropdown>
          </div>
          <div v-if="!collapsed[p.id]" class="task-list">
            <div
              v-for="t in tasksByProject(p)"
              :key="t.id"
              :class="['task-row', { active: selectedTaskId === t.id }]"
              @click="selectTask(t)"
            >
              <span class="status-dot" :class="t.status"></span>
              <div class="task-info">
                <div class="task-name">{{ t.name }}</div>
                <div class="task-meta">{{ t.source_table }} → {{ t.target_table }}</div>
              </div>
              <a-dropdown trigger="click" @click.stop>
                <a-button type="text" size="mini" class="task-menu" @click.stop>
                  <icon-more />
                </a-button>
                <template #content>
                  <a-doption @click="handleDeleteTask(t)" style="color:#F53F3F">
                    <icon-delete /> 删除
                  </a-doption>
                </template>
              </a-dropdown>
            </div>
            <div v-if="tasksByProject(p).length === 0" class="empty-tasks">暂无任务</div>
          </div>
        </div>
      </div>
      <div class="sider-footer">
        <a-button type="text" size="small" long @click="showProjectModal()">
          <template #icon><icon-plus /></template>
          新建项目
        </a-button>
      </div>
    </div>

    <!-- 右侧：内联画布 -->
    <div class="right-canvas">
      <SyncTaskCanvas
        v-if="canvasKey"
        :key="canvasKey"
        :task-id="selectedTaskId"
        :project-id="selectedProjectId"
        :projects="projects"
        @saved="onTaskSaved"
        @status-changed="onStatusChanged"
        @open-script="onOpenScript"
      />
    </div>

    <!-- 项目编辑弹窗 -->
    <a-modal
      v-model:visible="projectModalVisible"
      :title="editingProject?.id ? '编辑项目' : '新建项目'"
      @ok="handleProjectSubmit"
      :ok-loading="projectSubmitting"
      width="480px"
    >
      <a-form :model="projectForm" layout="vertical">
        <a-form-item label="项目名称">
          <a-input v-model="projectForm.name" placeholder="如：观星台 ETL" />
        </a-form-item>
        <a-form-item label="项目编码 (英文)" v-if="!editingProject?.id">
          <a-input v-model="projectForm.code" placeholder="如：guanxingtai" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model="projectForm.description" :auto-size="{ minRows: 2, maxRows: 4 }" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 删除项目弹窗 -->
    <a-modal
      v-model:visible="deleteProjectVisible"
      title="删除项目"
      @ok="confirmDeleteProject"
      :ok-loading="projectDeleting"
      width="440px"
      :ok-button-props="{ status: 'danger' }"
    >
      <p>项目 <strong>「{{ deletingProject?.name }}」</strong> 下有 {{ deletingProject?.task_count }} 个任务。</p>
      <a-form :model="{}" layout="vertical">
        <a-form-item label="任务处理">
          <a-radio-group v-model="deleteMode" direction="vertical">
            <a-radio value="unassign">移入「未分组」</a-radio>
            <a-radio value="move">迁移到其他项目</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item v-if="deleteMode === 'move'" label="目标项目">
          <a-select v-model="deleteMoveTo" placeholder="选择">
            <a-option
              v-for="p in projects.filter(x => x.id !== deletingProject?.id)"
              :key="p.id"
              :value="p.id"
            >{{ p.name }}</a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 脚本模式（保留旧向导） -->
    <SyncTaskWizard
      v-if="wizardEditingId !== undefined"
      v-model:visible="wizardVisible"
      :editing-id="wizardEditingId"
      :default-project-id="selectedProjectId"
      :projects="projects"
      @saved="onWizardSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconPlus, IconSearch, IconDown, IconRight, IconMore, IconEdit, IconDelete,
} from '@arco-design/web-vue/es/icon'
import {
  getSyncTasks, deleteSyncTask,
  getProjects, createProject, updateProject, deleteProject,
} from '../api'
import SyncTaskCanvas from '../components/SyncTaskCanvas.vue'
import SyncTaskWizard from '../components/SyncTaskWizard.vue'

const projects = ref<any[]>([])
const allTasks = ref<any[]>([])  // 全量任务，按 project_id 客户端分组
const searchKw = ref('')
const collapsed = reactive<Record<number, boolean>>({})

const selectedTaskId = ref<number | null>(null)
const selectedProjectId = ref<number | null>(null)
const canvasKey = ref<number>(1)  // 切换任务时强制重建 SyncTaskCanvas（初始 1 保证首屏直接渲染）

// 项目弹窗
const projectModalVisible = ref(false)
const projectSubmitting = ref(false)
const editingProject = ref<any>(null)
const projectForm = reactive({ name: '', code: '', description: '' })

// 删除项目
const deleteProjectVisible = ref(false)
const projectDeleting = ref(false)
const deletingProject = ref<any>(null)
const deleteMode = ref<'unassign' | 'move'>('unassign')
const deleteMoveTo = ref<number | undefined>(undefined)

// 脚本模式
const wizardVisible = ref(false)
const wizardEditingId = ref<number | null | undefined>(undefined)

// ---- 加载 ----
async function loadProjects() {
  try {
    const res: any = await getProjects()
    projects.value = res.items || []
    for (const p of projects.value) {
      if (collapsed[p.id] === undefined) collapsed[p.id] = false
    }
  } catch {}
}

async function loadAllTasks() {
  try {
    const res: any = await getSyncTasks({ page: 1, page_size: 500 })
    allTasks.value = res.items || []
  } catch {}
}

function tasksByProject(p: any) {
  const list = allTasks.value.filter(t => {
    const pid = t.project_id ?? null
    if (p.is_default) return pid === null || pid === p.id
    return pid === p.id
  })
  if (searchKw.value) {
    const kw = searchKw.value.toLowerCase()
    return list.filter(t =>
      (t.name || '').toLowerCase().includes(kw) ||
      (t.source_table || '').toLowerCase().includes(kw) ||
      (t.target_table || '').toLowerCase().includes(kw)
    )
  }
  return list
}

function toggleProject(pid: number) { collapsed[pid] = !collapsed[pid] }

function selectTask(t: any) {
  selectedTaskId.value = t.id
  selectedProjectId.value = t.project_id ?? null
  canvasKey.value++
}

function newTask() {
  selectedTaskId.value = null
  if (selectedProjectId.value == null && projects.value.length) {
    selectedProjectId.value = projects.value[0].id
  }
  canvasKey.value++
}

async function onTaskSaved(task: any) {
  await loadProjects()
  await loadAllTasks()
  // 切到刚保存的任务
  selectedTaskId.value = task.id
  selectedProjectId.value = task.project_id ?? null
  canvasKey.value++  // 让 Canvas 用新 task 重新初始化
}

// 上线/下线只刷新侧边栏状态点，不重建 Canvas
async function onStatusChanged(task: any) {
  await loadProjects()
  await loadAllTasks()
}

// ---- 项目 CRUD ----
function showProjectModal(p?: any) {
  editingProject.value = p || null
  if (p) {
    Object.assign(projectForm, { name: p.name, code: p.code, description: p.description || '' })
  } else {
    Object.assign(projectForm, { name: '', code: '', description: '' })
  }
  projectModalVisible.value = true
}

async function handleProjectSubmit() {
  if (!projectForm.name) { Message.warning('请输入项目名称'); return }
  if (!editingProject.value?.id && !projectForm.code) { Message.warning('请输入项目编码'); return }
  projectSubmitting.value = true
  try {
    if (editingProject.value?.id) {
      await updateProject(editingProject.value.id, {
        name: projectForm.name,
        description: projectForm.description,
      })
      Message.success('项目已更新')
    } else {
      await createProject({
        name: projectForm.name,
        code: projectForm.code,
        description: projectForm.description,
      })
      Message.success('项目已创建')
    }
    projectModalVisible.value = false
    await loadProjects()
  } catch {} finally {
    projectSubmitting.value = false
  }
}

function handleDeleteProject(p: any) {
  deletingProject.value = p
  deleteMode.value = 'unassign'
  deleteMoveTo.value = undefined
  deleteProjectVisible.value = true
}

async function confirmDeleteProject() {
  if (!deletingProject.value) return
  if (deleteMode.value === 'move' && !deleteMoveTo.value) {
    Message.warning('请选择目标项目'); return
  }
  projectDeleting.value = true
  try {
    const moveTo = deleteMode.value === 'move' ? deleteMoveTo.value : undefined
    await deleteProject(deletingProject.value.id, moveTo)
    Message.success('项目已删除')
    deleteProjectVisible.value = false
    if (selectedProjectId.value === deletingProject.value.id) {
      selectedProjectId.value = null
    }
    await loadProjects()
    await loadAllTasks()
  } catch {} finally {
    projectDeleting.value = false
  }
}

// ---- 任务删除 ----
async function handleDeleteTask(t: any) {
  try {
    await deleteSyncTask(t.id)
    Message.success('删除成功')
    if (selectedTaskId.value === t.id) {
      selectedTaskId.value = null
      canvasKey.value++
    }
    await loadProjects()
    await loadAllTasks()
  } catch {}
}

// ---- 脚本模式（旧向导） ----
function onOpenScript() {
  wizardEditingId.value = selectedTaskId.value
  wizardVisible.value = true
}

async function onWizardSaved() {
  wizardVisible.value = false
  wizardEditingId.value = undefined  // 卸载 SyncTaskWizard，避免遗留 modal teleport 拦截点击
  await loadProjects()
  await loadAllTasks()
}

// wizard 关闭时（用户点取消 / X / mask 关闭）也要卸载，避免 teleport 模态残留
watch(wizardVisible, (v) => {
  if (!v) wizardEditingId.value = undefined
})

onMounted(async () => {
  await loadProjects()
  await loadAllTasks()
  // 默认显示新建态
  newTask()
})
</script>

<style scoped>
.ide-layout {
  display: flex;
  height: calc(100vh - 110px);
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

/* 左侧 */
.left-sider {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #FAFBFC;
  border-right: 1px solid #E5E6EB;
}
.sider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #E5E6EB;
}
.sider-title { font-size: 14px; font-weight: 600; color: #1D2129; }
.sider-toolbar { padding: 8px 12px; border-bottom: 1px solid #F2F3F5; }
.tree-area { flex: 1; overflow-y: auto; padding: 6px 0; }
.sider-footer {
  padding: 6px 10px;
  border-top: 1px solid #E5E6EB;
  background: #F7F8FA;
}

/* 项目分组 */
.proj-group { margin-bottom: 2px; }
.proj-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #1D2129;
  border-radius: 6px;
  margin: 0 6px;
}
.proj-row:hover { background: #EAF1FF; }
.caret { font-size: 12px; color: #86909C; flex-shrink: 0; }
.proj-color-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.proj-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.proj-tag { margin-left: 4px; flex-shrink: 0; }
.proj-count {
  font-size: 11px;
  color: #86909C;
  background: #F2F3F5;
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
}
.proj-menu { opacity: 0; transition: opacity 0.15s; }
.proj-row:hover .proj-menu { opacity: 1; }

/* 任务列表 */
.task-list { padding-left: 22px; padding-right: 6px; }
.task-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin: 1px 0;
  transition: all 0.12s;
}
.task-row:hover { background: #fff; }
.task-row.active {
  background: #2B5AED;
  color: #fff;
}
.task-row.active .task-meta { color: rgba(255,255,255,0.7); }
.status-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #C9CDD4;
}
.status-dot.active { background: #00B42A; }
.status-dot.draft { background: #C9CDD4; }
.status-dot.paused { background: #FF7D00; }
.status-dot.error { background: #F53F3F; }
.task-info { flex: 1; min-width: 0; }
.task-name {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-meta {
  font-size: 11px;
  color: #86909C;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-menu { opacity: 0; transition: opacity 0.15s; flex-shrink: 0; }
.task-row:hover .task-menu { opacity: 1; }
.task-row.active .task-menu { opacity: 0.8; color: #fff; }

.empty-tasks {
  padding: 12px;
  text-align: center;
  color: #C9CDD4;
  font-size: 12px;
}

/* 右侧画布 */
.right-canvas {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}
</style>
