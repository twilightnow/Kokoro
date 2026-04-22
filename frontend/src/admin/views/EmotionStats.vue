<template>
  <div>
    <h1 class="page-title">情绪统计</h1>

    <!-- 时间范围选择 -->
    <div style="display:flex; gap:8px; margin-bottom:16px; align-items:center">
      <span style="font-size:12px; color:#6b7280">时间范围：</span>
      <button
        v-for="d in [7, 30, 90]"
        :key="d"
        class="btn btn-sm"
        :class="days === d ? 'btn-primary' : 'btn-secondary'"
        @click="days = d; loadStats()"
      >
        {{ d }} 天
      </button>
    </div>

    <div v-if="error" class="banner-error">{{ error }}</div>
    <div v-if="loading" class="loading">加载中…</div>

    <template v-else>
      <!-- 情绪时序折线图（简易 SVG 版） -->
      <div class="card mt-4">
        <div class="card-title">情绪时序</div>
        <div v-if="!emotionData?.series?.length" class="empty">暂无数据</div>
        <div v-else class="chart-wrap">
          <svg :width="chartW" :height="chartH" class="chart-svg">
            <!-- 网格线 -->
            <line
              v-for="y in yGridLines"
              :key="y"
              :x1="chartPad" :y1="y" :x2="chartW - 10" :y2="y"
              stroke="#f3f4f6" stroke-width="1"
            />
            <!-- 情绪折线 -->
            <polyline
              v-for="mood in moods"
              :key="mood.key"
              :points="seriesPoints(mood.key)"
              :stroke="mood.color"
              stroke-width="2"
              fill="none"
            />
            <!-- X 轴日期标签（每隔几天显示一个） -->
            <text
              v-for="(d, i) in xLabels"
              :key="i"
              :x="d.x"
              :y="chartH - 4"
              fill="#9ca3af"
              font-size="10"
              text-anchor="middle"
            >{{ d.label }}</text>
          </svg>
          <!-- 图例 -->
          <div class="legend">
            <span v-for="mood in moods" :key="mood.key" class="legend-item">
              <span class="legend-dot" :style="{ background: mood.color }"></span>
              {{ mood.label }}
            </span>
          </div>
        </div>
      </div>

      <!-- 触发词热力表 -->
      <div class="card mt-4">
        <div style="display:flex; justify-content:space-between; margin-bottom:12px">
          <div class="card-title" style="margin:0">触发词排行（Top {{ topN }}）</div>
        </div>
        <div v-if="!triggerData?.items?.length" class="empty">暂无数据</div>
        <div class="table-wrap" v-else>
          <table>
            <thead>
              <tr><th>触发词</th><th>情绪</th><th>次数</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in triggerData.items" :key="item.word">
                <td><code>{{ item.word }}</code></td>
                <td>
                  <span class="badge" :class="moodBadge(item.emotion)">{{ item.emotion }}</span>
                </td>
                <td>{{ item.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

const days = ref(30)
const topN = 10
const loading = ref(false)
const error = ref('')
const emotionData = ref<any>(null)
const triggerData = ref<any>(null)

const moods = [
  { key: 'normal', label: '平静', color: '#94a3b8' },
  { key: 'happy', label: '开心', color: '#fbbf24' },
  { key: 'angry', label: '生气', color: '#ef4444' },
  { key: 'shy', label: '害羞', color: '#f9a8d4' },
  { key: 'cold', label: '冷淡', color: '#60a5fa' },
]

const chartW = 700
const chartH = 200
const chartPad = 40
const chartBottom = 20

const maxVal = computed(() => {
  if (!emotionData.value?.series) return 1
  let max = 1
  for (const d of emotionData.value.series) {
    for (const m of moods) {
      if ((d[m.key] ?? 0) > max) max = d[m.key]
    }
  }
  return max
})

const yGridLines = computed(() => {
  const lines = []
  for (let i = 0; i <= 4; i++) {
    lines.push(chartPad + (i / 4) * (chartH - chartPad - chartBottom))
  }
  return lines
})

function seriesX(index: number, total: number): number {
  if (total <= 1) return chartPad
  return chartPad + (index / (total - 1)) * (chartW - chartPad - 10)
}

function seriesY(value: number): number {
  const height = chartH - chartPad - chartBottom
  return chartPad + (1 - value / maxVal.value) * height
}

function seriesPoints(moodKey: string): string {
  const series = emotionData.value?.series ?? []
  return series
    .map((d: any, i: number) => `${seriesX(i, series.length)},${seriesY(d[moodKey] ?? 0)}`)
    .join(' ')
}

const xLabels = computed(() => {
  const series = emotionData.value?.series ?? []
  const step = Math.max(1, Math.floor(series.length / 7))
  return series
    .filter((_: any, i: number) => i % step === 0 || i === series.length - 1)
    .map((d: any) => {
      const originalIdx = series.indexOf(d)
      return {
        x: seriesX(originalIdx, series.length),
        label: d.date?.slice(5), // MM-DD
      }
    })
})

function moodBadge(emotion: string) {
  const map: Record<string, string> = {
    happy: 'badge-yellow',
    angry: 'badge-red',
    shy: 'badge-blue',
    cold: 'badge-gray',
    normal: 'badge-gray',
  }
  return map[emotion] ?? 'badge-gray'
}

async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    ;[emotionData.value, triggerData.value] = await Promise.all([
      api.emotionStats(days.value),
      api.triggerStats(topN, days.value),
    ])
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<style scoped>
.chart-wrap {
  overflow-x: auto;
}

.chart-svg {
  display: block;
  max-width: 100%;
}

.legend {
  display: flex;
  gap: 14px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #374151;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
</style>
