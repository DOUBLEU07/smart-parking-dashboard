<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { BarElement, CategoryScale, Chart, LinearScale, Tooltip } from 'chart.js'

Chart.register(BarElement, CategoryScale, LinearScale, Tooltip)

/** Single-series bar chart: no legend (the card title names the series). */
const props = defineProps({
  labels: { type: Array, required: true },
  values: { type: Array, required: true },
  color: { type: String, default: '#2F6B5E' },
  highlight: { type: Number, default: -1 }, // index drawn in the accent color
  highlightColor: { type: String, default: '#B4501F' },
  format: { type: Function, default: (v) => String(v) },
  tooltipTitle: { type: Function, default: null },
  height: { type: Number, default: 240 },
})

const INK_MUTED = '#6B6257'
const GRID = '#EDE7DA'

const data = computed(() => ({
  labels: props.labels,
  datasets: [{
    data: props.values,
    backgroundColor: props.values.map((_, i) => (i === props.highlight ? props.highlightColor : props.color)),
    hoverBackgroundColor: props.values.map((_, i) => (i === props.highlight ? '#8C3D16' : '#245347')),
    borderRadius: { topLeft: 4, topRight: 4 },
    borderSkipped: 'bottom',
    maxBarThickness: 28,
    categoryPercentage: 0.8,
    barPercentage: 0.85,
  }],
}))

const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 300 },
  interaction: { mode: 'index', intersect: false }, // hit area = whole column, not just the bar
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#16211D',
      titleColor: '#F6F4EE',
      bodyColor: '#F6F4EE',
      padding: 10,
      cornerRadius: 8,
      displayColors: false,
      titleFont: { family: 'IBM Plex Sans Thai', weight: '600' },
      bodyFont: { family: 'IBM Plex Sans Thai' },
      callbacks: {
        title: (items) => (props.tooltipTitle ? props.tooltipTitle(items[0].dataIndex) : items[0].label),
        label: (item) => props.format(item.raw),
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { color: '#DDD3BF' },
      ticks: { color: INK_MUTED, font: { family: 'IBM Plex Sans Thai', size: 11 }, maxRotation: 0, autoSkipPadding: 8 },
    },
    y: {
      beginAtZero: true,
      grid: { color: GRID, drawTicks: false },
      border: { display: false },
      ticks: { color: INK_MUTED, font: { family: 'IBM Plex Sans Thai', size: 11 }, padding: 8, maxTicksLimit: 5,
               callback: (v) => props.format(v) },
    },
  },
}))
</script>

<template>
  <div :style="{ height: `${height}px` }">
    <Bar :data="data" :options="options" />
  </div>
</template>
