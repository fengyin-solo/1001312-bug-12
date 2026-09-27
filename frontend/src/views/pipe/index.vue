<template>
  <section class="page" data-module="pipe">
    <header class="page-head">
      <div>
        <h2>管网巡查管理</h2>
        <p class="page-desc">待巡查、巡查中、已复核三段分开存放；巡查记录只落在对应的巡查编号上。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记管网巡查</button>
        <button class="btn" type="button" @click="openSupplementary">补录巡查记录</button>
        <button class="btn" type="button" @click="exportRows">导出管网巡查清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>巡查编号</span>
        <input v-model="filters.keyword" placeholder="按巡查编号检索" />
      </label>
      <label class="filter-item">
        <span>进度</span>
        <select v-model="filters.status">
          <option value="">全部进度</option>
          <option v-for="stage in stages" :key="stage" :value="stage">{{ stage }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button
              v-if="row.巡查状态 === '待巡查'"
              class="link"
              type="button"
              @click="runAction('开始巡查', row)"
            >
              开始巡查
            </button>
            <button
              v-if="row.巡查状态 !== '已复核'"
              class="link"
              type="button"
              @click="openRecord(row)"
            >
              填写记录
            </button>
            <button
              v-if="row.巡查状态 === '巡查中'"
              class="link"
              type="button"
              @click="openReview(row)"
            >
              复核
            </button>
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无管网巡查数据，可先登记管网巡查</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条管网巡查记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal-card">
        <h3>登记管网巡查</h3>
        <label v-for="field in baseFields" :key="field" class="form-item">
          <span>{{ field }} *</span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitCreate">提交登记</button>
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="recordVisible && recordTarget" class="modal-mask" @click.self="recordVisible = false">
      <div class="modal-card">
        <h3>填写巡查记录 · {{ recordTarget.巡查编号 }}</h3>
        <p class="modal-desc">
          巡查路段：{{ recordTarget.巡查路段 }} · 巡查人员：{{ recordTarget.巡查人员 }} · 巡查日期：{{ recordTarget.巡查日期 }}
        </p>
        <label class="form-item">
          <span>管线状况 *</span>
          <input v-model="recordForm.管线状况" placeholder="必填，为空不允许提交" />
        </label>
        <label class="form-item">
          <span>井盖状况</span>
          <input v-model="recordForm.井盖状况" placeholder="选填" />
        </label>
        <label class="form-item">
          <span>异常描述</span>
          <textarea v-model="recordForm.异常描述" placeholder="选填，仅保存到当前巡查编号"></textarea>
        </label>
        <p v-if="recordError" class="error-text">{{ recordError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitRecord">提交记录</button>
          <button class="btn ghost" type="button" @click="recordVisible = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="reviewVisible && reviewRow" class="modal-mask" @click.self="reviewVisible = false">
      <div class="modal-card">
        <h3>复核巡查记录 · {{ reviewRow.巡查编号 }}</h3>
        <dl class="detail-grid">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ reviewRow[field] || '—' }}</dd>
          </template>
        </dl>
        <p class="modal-desc">复核通过后记录进入已复核，异常描述不允许再修改。</p>
        <p v-if="reviewError" class="error-text">{{ reviewError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitReview">确认复核</button>
          <button class="btn ghost" type="button" @click="reviewVisible = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="suppVisible" class="modal-mask" @click.self="closeSupplementary">
      <div class="modal-card wide">
        <h3>补录巡查记录</h3>
        <p class="modal-desc">每条独立校验；被阻断的条目会留在列表里，可只重试该条，不影响已成功的记录。</p>
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="field in suppFields" :key="field">{{ field }}</th>
              <th>补录状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in suppItems" :key="index">
              <td v-for="field in suppFields" :key="field">
                <input v-model="item.values[field]" :disabled="item.done" :placeholder="field" />
              </td>
              <td>
                <span v-if="item.done" class="ok-text">已补录</span>
                <span v-else-if="item.error" class="error-text">{{ item.error }}</span>
                <span v-else class="muted-text">待提交</span>
              </td>
              <td class="row-actions">
                <button v-if="item.error" class="link" type="button" @click="retrySupplementary(index)">重试本条</button>
                <button v-if="!item.done" class="link" type="button" @click="suppItems.splice(index, 1)">移除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="suppMessage" class="error-text">{{ suppMessage }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="addSupplementary">再加一条</button>
          <button class="btn primary" type="button" @click="submitSupplementary">提交补录</button>
          <button class="btn ghost" type="button" @click="closeSupplementary">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface SuppItem {
  values: Record<string, string>
  done: boolean
  error: string
}

interface SuppItemResult {
  ok: boolean
  code: string
  reason: string
}

const ENDPOINT = '/api/pipe'
const stages = ['待巡查', '巡查中', '已复核']
const columns = ['巡查编号', '巡查路段', '巡查人员', '巡查日期', '管线状况', '井盖状况', '异常描述', '巡查状态']
const baseFields = ['巡查编号', '巡查路段', '巡查人员', '巡查日期']
const recordFields = ['管线状况', '井盖状况', '异常描述']
const detailFields = [...baseFields, ...recordFields, '巡查状态']
const suppFields = [...baseFields, ...recordFields]

const router = useRouter()
const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref(stages.map((label) => ({ label, value: 0 })))
const errorMessage = ref('')
const filters = reactive({ keyword: '', status: '' })

const createVisible = ref(false)
const createForm = reactive<Record<string, string>>({})
const createError = ref('')

const recordVisible = ref(false)
const recordTarget = ref<Row | null>(null)
const recordForm = reactive<Record<string, string>>({ 管线状况: '', 井盖状况: '', 异常描述: '' })
const recordError = ref('')

const reviewVisible = ref(false)
const reviewRow = ref<Row | null>(null)
const reviewError = ref('')

const suppVisible = ref(false)
const suppItems = ref<SuppItem[]>([])
const suppMessage = ref('')

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  for (const field of baseFields) createForm[field] = ''
  createError.value = ''
  createVisible.value = true
}

async function submitCreate() {
  createError.value = ''
  try {
    const payload = await postJson(`${ENDPOINT}`, { values: { ...createForm } })
    if (!payload.ok) {
      createError.value = payload.message || '管网巡查登记被阻断'
      return
    }
    createVisible.value = false
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '管网巡查登记失败'
  }
}

function openRecord(row: Row) {
  recordTarget.value = row
  recordForm.管线状况 = String(row.管线状况 ?? '')
  recordForm.井盖状况 = String(row.井盖状况 ?? '')
  recordForm.异常描述 = String(row.异常描述 ?? '')
  recordError.value = ''
  recordVisible.value = true
}

async function submitRecord() {
  if (!recordTarget.value) return
  recordError.value = ''
  if (!recordForm.管线状况.trim()) {
    recordError.value = `巡查编号 ${recordTarget.value.巡查编号} 管线状况为空，不允许提交`
    return
  }
  try {
    const payload = await postJson(`${ENDPOINT}/${recordTarget.value.id}/actions`, {
      values: { action: '填写记录', ...recordForm },
    })
    if (!payload.ok) {
      recordError.value = payload.message || '巡查记录提交被阻断'
      return
    }
    recordVisible.value = false
    await reload()
  } catch (error) {
    recordError.value = error instanceof Error ? error.message : '巡查记录提交失败'
  }
}

async function openReview(row: Row) {
  reviewError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('巡查记录读取失败，请刷新列表后重试')
    }
    reviewRow.value = await response.json()
    reviewVisible.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查记录读取失败'
  }
}

async function submitReview() {
  if (!reviewRow.value) return
  reviewError.value = ''
  try {
    const payload = await postJson(`${ENDPOINT}/${reviewRow.value.id}/actions`, {
      values: { action: '复核' },
    })
    if (!payload.ok) {
      reviewError.value = payload.message || '复核被阻断'
      return
    }
    reviewVisible.value = false
    await reload()
  } catch (error) {
    reviewError.value = error instanceof Error ? error.message : '复核失败'
  }
}

function openDetail(row: Row) {
  void router.push(`/pipe/${row.id}`)
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const payload = await postJson(`${ENDPOINT}/${row.id}/actions`, { values: { action } })
    if (!payload.ok) {
      throw new Error(payload.message || `管网巡查动作「${action}」被阻断`)
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '管网巡查操作失败'
  }
}

function openSupplementary() {
  suppItems.value = [newSuppItem()]
  suppMessage.value = ''
  suppVisible.value = true
}

function newSuppItem(): SuppItem {
  return { values: Object.fromEntries(suppFields.map((field) => [field, ''])), done: false, error: '' }
}

function addSupplementary() {
  suppItems.value.push(newSuppItem())
}

async function submitSupplementary() {
  suppMessage.value = ''
  const pending = suppItems.value.filter((item) => !item.done)
  if (!pending.length) {
    suppMessage.value = '没有待提交的补录记录'
    return
  }
  try {
    const payload = await postJson(`${ENDPOINT}/supplementary`, {
      items: pending.map((item) => item.values),
    })
    applySuppResults(pending, payload.results ?? [])
    suppMessage.value = payload.message || ''
    await reload()
  } catch (error) {
    suppMessage.value = error instanceof Error ? error.message : '补录提交失败'
  }
}

async function retrySupplementary(index: number) {
  const item = suppItems.value[index]
  if (!item || item.done) return
  item.error = ''
  suppMessage.value = ''
  try {
    const payload = await postJson(`${ENDPOINT}/supplementary`, { items: [item.values] })
    applySuppResults([item], payload.results ?? [])
    suppMessage.value = payload.message || ''
    await reload()
  } catch (error) {
    item.error = error instanceof Error ? error.message : '补录重试失败'
  }
}

function applySuppResults(items: SuppItem[], results: SuppItemResult[]) {
  results.forEach((result, index) => {
    const item = items[index]
    if (!item) return
    if (result.ok) {
      item.done = true
      item.error = ''
    } else {
      item.error = result.reason || '补录被阻断'
    }
  })
}

function closeSupplementary() {
  suppVisible.value = false
  void reload()
}

async function postJson(path: string, body: Record<string, unknown>): Promise<Record<string, any>> {
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.detail ?? `接口返回 ${response.status}，操作未生效`)
  }
  return payload ?? {}
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.keyword) query.set('keyword', filters.keyword)
  if (filters.status) query.set('status', filters.status)
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok || !statsResponse.ok) {
      throw new Error('管网巡查列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const counts = await statsResponse.json()
    stats.value = stages.map((label) => ({ label, value: Number(counts[label] ?? 0) }))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '管网巡查列表读取失败'
  }
}

onMounted(reload)
</script>
