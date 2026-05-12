<template>
  <div class="page">
    <div class="glass-card page-header">
      <div>
        <h3 class="page-title">工作流管理</h3>
        <p class="page-desc">Portal 统一工作流编排与调度</p>
      </div>
    </div>

    <div class="glass-card empty-card">
      <div class="empty-illustration">⚙️</div>
      <h4 class="empty-title">工作流系统升级中</h4>
      <p class="empty-desc">
        平台正在切换到 <strong>Portal First</strong> 架构,工作流配置将由 Portal 统一管理,
        通过 DSL Translator 翻译为底层调度引擎的 DAG。
      </p>
      <div class="phase-progress">
        <div class="phase-item done">
          <div class="phase-dot"></div>
          <div class="phase-text">
            <div class="phase-name">数据源管理</div>
            <div class="phase-status">已上线</div>
          </div>
        </div>
        <div class="phase-item active">
          <div class="phase-dot"></div>
          <div class="phase-text">
            <div class="phase-name">Component 模型</div>
            <div class="phase-status">Phase 3 · 开发中</div>
          </div>
        </div>
        <div class="phase-item">
          <div class="phase-dot"></div>
          <div class="phase-text">
            <div class="phase-name">线性 Workflow 编辑器</div>
            <div class="phase-status">Phase 4 · 待启动</div>
          </div>
        </div>
        <div class="phase-item">
          <div class="phase-dot"></div>
          <div class="phase-text">
            <div class="phase-name">DSL Translator</div>
            <div class="phase-status">Phase 6 · 待启动</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 工作流管理在新架构下重构中,当前页面为占位
// 详见 Phase 3 (Component) → Phase 4 (Workflow) → Phase 6 (DSL Translator)
</script>

<style scoped>
.page { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.page-header { padding: 20px 24px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 18px; font-weight: 600; color: #1D2129; }
.page-desc { margin: 4px 0 0; font-size: 13px; color: #86909C; }

.empty-card {
  padding: 60px 40px;
  text-align: center;
  max-width: 720px;
  margin: 24px auto;
}
.empty-illustration {
  font-size: 56px;
  margin-bottom: 16px;
  opacity: 0.85;
}
.empty-title {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: 600;
  color: #1D2129;
}
.empty-desc {
  margin: 0 0 32px;
  font-size: 14px;
  line-height: 1.7;
  color: #4E5969;
}
.empty-desc strong {
  color: #2B5AED;
}

.phase-progress {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 480px;
  margin: 0 auto;
  text-align: left;
}
.phase-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #F7F8FA;
  border-radius: 8px;
  transition: all 0.15s;
}
.phase-item.done {
  background: rgba(0, 180, 42, 0.06);
}
.phase-item.active {
  background: rgba(43, 90, 237, 0.06);
}
.phase-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #C9CDD4;
  flex-shrink: 0;
}
.phase-item.done .phase-dot { background: #00B42A; }
.phase-item.active .phase-dot {
  background: #2B5AED;
  box-shadow: 0 0 0 4px rgba(43, 90, 237, 0.15);
}
.phase-text { flex: 1; }
.phase-name {
  font-size: 14px;
  font-weight: 500;
  color: #1D2129;
}
.phase-status {
  font-size: 12px;
  color: #86909C;
  margin-top: 2px;
}
.phase-item.done .phase-status { color: #00B42A; }
.phase-item.active .phase-status { color: #2B5AED; font-weight: 500; }
</style>
