<template>
  <section class="page" data-module="pipe-detail">
    <header class="page-head">
      <div>
        <h2>管网巡查明细</h2>
        <p class="page-desc">进度、业务字段均取自同一条巡查记录，与列表页、复核弹窗保持一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <article v-if="entry" class="detail-card">
      <div class="detail-head">
        <h3>{{ entry['巡查编号'] }}</h3>
        <span class="badge" :class="badgeClass(entry.status)">{{ entry.status }}</span>
      </div>
      <dl class="detail-list detail-card-list">
        <div><dt>巡查路段</dt><dd>{{ entry['巡查路段'] || '—' }}</dd></div>
        <div><dt>巡查人员</dt><dd>{{ entry['巡查人员'] || '—' }}</dd></div>
        <div><dt>巡查日期</dt><dd>{{ entry['巡查日期'] || '—' }}</dd></div>
        <div class="detail-wide"><dt>管线状况</dt><dd>{{ entry['管线状况'] || '—' }}</dd></div>
        <div class="detail-wide"><dt>井盖状况</dt><dd>{{ entry['井盖状况'] || '—' }}</dd></div>
        <div class="detail-wide"><dt>异常描述</dt><dd>{{ entry['异常描述'] || '—' }}</dd></div>
      </dl>
      <p v-if="entry.status === '已复核'" class="modal-tip">该记录已复核，异常描述已锁定留档，不允许再修改。</p>
    </article>

    <p v-else-if="!loading" class="error-text">{{ errorMessage || '未找到该巡查记录' }}</p>
    <p v-else class="page-desc">正在加载巡查记录…</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string> & { id: number; status: string }

const route = useRoute()
const router = useRouter()

const entry = ref<Row | null>(null)
const loading = ref(true)
const errorMessage = ref('')

function badgeClass(status: string) {
  return {
    待巡查: 'badge-pending',
    巡查中: 'badge-doing',
    已复核: 'badge-done',
  }[status] ?? ''
}

function goBack() {
  void router.push('/pipe')
}

onMounted(async () => {
  const id = Number(route.params.id)
  if (!Number.isFinite(id)) {
    loading.value = false
    errorMessage.value = '巡查编号无效'
    return
  }
  try {
    const response = await request(`/api/pipe/${id}`)
    if (!response.ok) throw new Error('巡查记录不存在或已归档')
    entry.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查记录读取失败'
  } finally {
    loading.value = false
  }
})
</script>
