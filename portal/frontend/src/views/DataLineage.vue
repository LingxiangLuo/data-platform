<template>
  <div class="page">
    <div class="glass-card page-header">
      <div>
        <h3 class="page-title">数据血缘</h3>
        <p class="page-desc">追踪数据流转关系与依赖</p>
      </div>
    </div>

    <div class="glass-card lineage-card">
      <div class="lineage-diagram">
        <div class="lineage-layer">
          <div class="layer-label">数据源</div>
          <div class="layer-items">
            <div class="node source">
              <div class="node-badge" style="background: #EFF4FF; color: #2B5AED;">MySQL</div>
              <div class="node-name">生产库-用户中心</div>
              <div class="node-meta">t_user, t_order</div>
            </div>
            <div class="node source">
              <div class="node-badge" style="background: #F5E8FF; color: #7B61FF;">SQLServer</div>
              <div class="node-name">业务库-交易系统</div>
              <div class="node-meta">trade_record, account</div>
            </div>
          </div>
        </div>

        <div class="arrow-group">
          <div class="arrow-line"></div>
          <div class="arrow-label">DataX 同步</div>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2v12m0 0l-3-3m3 3l3-3" stroke="#2B5AED" stroke-width="1.5" stroke-linecap="round"/></svg>
        </div>

        <div class="lineage-layer">
          <div class="layer-label">ODS 贴源层</div>
          <div class="layer-items">
            <div class="node intermediate">
              <div class="node-badge" style="background: #E8FFF3; color: #00B42A;">ODS</div>
              <div class="node-name">ods_user</div>
              <div class="node-meta">用户数据贴源表</div>
            </div>
            <div class="node intermediate">
              <div class="node-badge" style="background: #E8FFF3; color: #00B42A;">ODS</div>
              <div class="node-name">ods_trade</div>
              <div class="node-meta">交易数据贴源表</div>
            </div>
          </div>
        </div>

        <div class="arrow-group">
          <div class="arrow-line"></div>
          <div class="arrow-label">DolphinScheduler ETL</div>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2v12m0 0l-3-3m3 3l3-3" stroke="#2B5AED" stroke-width="1.5" stroke-linecap="round"/></svg>
        </div>

        <div class="lineage-layer">
          <div class="layer-label">DIM / DW 应用层</div>
          <div class="layer-items">
            <div class="node target">
              <div class="node-badge" style="background: #FFF7E8; color: #FF7D00;">DIM</div>
              <div class="node-name">dim_user</div>
              <div class="node-meta">用户维度表</div>
            </div>
            <div class="node target">
              <div class="node-badge" style="background: #FFF7E8; color: #FF7D00;">DW</div>
              <div class="node-name">dw_trade_daily</div>
              <div class="node-meta">交易日汇总表</div>
            </div>
          </div>
        </div>
      </div>

      <a-alert type="info" style="margin-top: 24px;">
        数据血缘由 OpenMetadata 自动采集。添加数据源后，系统将自动分析表级和字段级血缘关系。
      </a-alert>
    </div>
  </div>
</template>

<style scoped>
.page { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.page-header { padding: 20px 24px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 18px; font-weight: 600; color: #1D2129; }
.page-desc { margin: 4px 0 0; font-size: 13px; color: #86909C; }

.lineage-card { padding: 28px; }
.lineage-diagram { display: flex; flex-direction: column; align-items: center; gap: 0; }
.lineage-layer { width: 100%; max-width: 550px; text-align: center; }
.layer-label { font-size: 11px; color: #86909C; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; font-weight: 600; }
.layer-items { display: flex; gap: 20px; justify-content: center; }

.node {
  background: #FFFFFF;
  border: 1px solid #E5E8ED;
  border-radius: 10px;
  padding: 16px 22px;
  min-width: 180px;
  text-align: center;
  transition: all 0.2s;
}
.node:hover { border-color: #D6E4FF; box-shadow: 0 4px 12px rgba(43,90,237,0.08); }
.node-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 8px;
}
.node-name { font-size: 13px; font-weight: 600; color: #1D2129; margin-bottom: 2px; }
.node-meta { font-size: 11px; color: #86909C; }

.arrow-group { display: flex; flex-direction: column; align-items: center; padding: 10px 0; }
.arrow-line { width: 1px; height: 20px; background: linear-gradient(to bottom, #E5E8ED, #2B5AED); }
.arrow-label { font-size: 10px; color: #2B5AED; background: #EFF4FF; padding: 2px 10px; border-radius: 10px; margin: 4px 0; font-weight: 500; }
</style>
