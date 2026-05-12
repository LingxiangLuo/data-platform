<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-title">调度任务</div>
      <div class="page-desc">查看与管理所有调度周期任务</div>
    </div>
    <div class="coming-soon">
      <div class="cs-icon"><icon-calendar style="font-size: 48px; color: #C9CDD4;" /></div>
      <div class="cs-title">调度任务 — 即将上线</div>
      <div class="cs-desc">该功能正在开发中，将展示所有 Cron 调度配置及下次执行时间</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { IconCalendar } from '@arco-design/web-vue/es/icon'
</script>

<style scoped>
.page-container { padding: 0; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 20px; font-weight: 600; color: #1D2129; }
.page-desc { font-size: 13px; color: #86909C; margin-top: 4px; }
.coming-soon {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 400px; background: #fff; border-radius: 12px; gap: 12px;
}
.cs-title { font-size: 16px; font-weight: 500; color: #4E5969; }
.cs-desc { font-size: 13px; color: #86909C; max-width: 360px; text-align: center; }
</style>
