<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import DagCanvas from '../components/dag/DagCanvas.vue'
import DagNodePanel from '../components/dag/DagNodePanel.vue'
import DagToolbar from '../components/dag/DagToolbar.vue'
import { getWorkflow, createWorkflow, updateWorkflow, testWorkflow, publishWorkflow, runWorkflow } from '../api'

interface DagNode { id: string; component_id: number; name: string; position: { x: number; y: number }; skip: boolean }
interface DagEdge { id: string; source: string; target: string }

const route = useRoute()
const router = useRouter()
const dagCanvas = ref<InstanceType<typeof DagCanvas>>()

const workflowId = ref<number | null>(null)
const workflowName = ref('')
const workflowDesc = ref('')
const workflowStatus = ref('draft')
const cronExpression = ref('')
const dagNodes = ref<DagNode[]>([])
const dagEdges = ref<DagEdge[]>([])
const loading = ref(false)

onMounted(async () => {
  const id = route.params.id as string
  if (id && id !== 'new') {
    workflowId.value = parseInt(id)
    await loadWorkflow()
  }
})

async function loadWorkflow() {
  if (!workflowId.value) return
  const res: any = await getWorkflow(workflowId.value)
  workflowName.value = res.name
  workflowDesc.value = res.description || ''
  workflowStatus.value = res.status
  cronExpression.value = res.cron_expression || ''
  if (res.dag && res.dag.nodes) {
    dagNodes.value = res.dag.nodes
    dagEdges.value = res.dag.edges || []
  } else if (res.steps && res.steps.length) {
    // 兼容旧线性数据：转为 DAG
    dagNodes.value = res.steps.map((s: any, i: number) => ({
      id: `node-${i+1}`, component_id: s.component_id, name: s.name || s.component_name,
      position: { x: 200 + i * 220, y: 200 }, skip: false,
    }))
    dagEdges.value = res.steps.slice(1).map((s: any, i: number) => ({
      id: `edge-${i+1}`, source: `node-${i+1}`, target: `node-${i+2}`,
    }))
  }
}

function onDagUpdate(dag: { nodes: DagNode[]; edges: DagEdge[] }) {
  dagNodes.value = dag.nodes
  dagEdges.value = dag.edges
}

async function handleSave() {
  if (!workflowName.value.trim()) { Message.warning('请输入工作流名称'); return }
  loading.value = true
  try {
    const payload = {
      name: workflowName.value,
      description: workflowDesc.value || null,
      cron_expression: cronExpression.value || null,
      dag: { nodes: dagNodes.value, edges: dagEdges.value },
    }
    if (workflowId.value) {
      await updateWorkflow(workflowId.value, payload)
      Message.success('保存成功')
    } else {
      const res: any = await createWorkflow(payload)
      workflowId.value = res.id
      workflowStatus.value = res.status
      router.replace(`/workflows/${res.id}/edit`)
      Message.success('创建成功')
    }
    await loadWorkflow()
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '保存失败')
  } finally { loading.value = false }
}

async function handleTest() {
  if (!workflowId.value) { Message.warning('请先保存'); return }
  try {
    await testWorkflow(workflowId.value)
    workflowStatus.value = 'tested'
    Message.success('测试通过')
  } catch (e: any) { Message.error(e?.response?.data?.detail || '测试失败') }
}

async function handlePublish() {
  if (!workflowId.value) return
  try {
    await publishWorkflow(workflowId.value)
    workflowStatus.value = 'online'
    Message.success('发布成功')
  } catch (e: any) { Message.error(e?.response?.data?.detail || '发布失败') }
}

async function handleRun() {
  if (!workflowId.value) return
  try {
    await runWorkflow(workflowId.value)
    Message.success('已触发运行')
  } catch (e: any) { Message.error(e?.response?.data?.detail || '运行失败') }
}

function handleBack() { router.push('/workflows') }
function handleAutoLayout() { dagCanvas.value?.autoLayout() }
</script>

<template>
  <div class="workflow-editor">
    <DagToolbar
      :workflow-name="workflowName"
      :status="workflowStatus"
      @save="handleSave" @test="handleTest" @publish="handlePublish"
      @run="handleRun" @back="handleBack" @auto-layout="handleAutoLayout"
    />
    <div class="workflow-editor__meta">
      <input v-model="workflowName" placeholder="工作流名称" class="workflow-editor__name-input" />
      <input v-model="cronExpression" placeholder="CRON 表达式（可选）" class="workflow-editor__cron-input" />
    </div>
    <div class="workflow-editor__body">
      <DagNodePanel />
      <DagCanvas ref="dagCanvas" :nodes="dagNodes" :edges="dagEdges" @update="onDagUpdate" />
    </div>
  </div>
</template>

<style scoped>
.workflow-editor { display: flex; flex-direction: column; height: 100vh; background: #f7f8fa; }
.workflow-editor__meta { display: flex; gap: 12px; padding: 8px 16px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.workflow-editor__name-input { flex: 1; max-width: 300px; padding: 6px 10px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 14px; }
.workflow-editor__cron-input { width: 200px; padding: 6px 10px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; color: #666; }
.workflow-editor__body { flex: 1; display: flex; overflow: hidden; }
</style>
