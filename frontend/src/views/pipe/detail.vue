<template>
  <section class="page" data-module="pipe">
    <header class="page-head">
      <div>
        <h2>巡查记录详情</h2>
        <p class="page-desc">详情页进度与列表页、复核弹窗同源，均以分段存储的进度为准。</p>
      </div>
      <button class="btn" type="button" @click="goBack">返回列表</button>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    <dl v-if="entry" class="detail-grid">
      <template v-for="field in fields" :key="field">
        <dt>{{ field }}</dt>
        <dd>{{ entry[field] || '—' }}</dd>
      </template>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Entry = Record<string, string | number | null>

const fields = ['巡查编号', '巡查路段', '巡查人员', '巡查日期', '管线状况', '井盖状况', '异常描述', '巡查状态']

const route = useRoute()
const router = useRouter()
const entry = ref<Entry | null>(null)
const errorMessage = ref('')

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/pipe/${route.params.id}`)
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ?? '巡查记录读取失败')
    }
    entry.value = payload
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查记录读取失败'
  }
}

function goBack() {
  void router.push('/pipe')
}

onMounted(load)
</script>
