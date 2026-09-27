<template>
  <section class="page" data-module="pipe">
    <header class="page-head">
      <div>
        <h2>管网巡查管理</h2>
        <p class="page-desc">待巡查、巡查中、已复核三段分开管理；巡查编号与巡查记录一一对应，复核后异常描述锁定留档。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记管网巡查</button>
        <button class="btn" type="button" @click="openBackfill">批量补录</button>
        <button class="btn" type="button" @click="exportRows">导出管网巡查清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.key" class="stat-card">
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
        <span>巡查路段</span>
        <input v-model="filters.road" placeholder="按巡查路段检索" />
      </label>
      <label class="filter-item">
        <span>巡查人员</span>
        <input v-model="filters.inspector" placeholder="按巡查人员检索" />
      </label>
      <label class="filter-item">
        <span>巡查状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
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
          <td v-for="column in columns" :key="column">
            <template v-if="column === '巡查状态'">
              <span class="badge" :class="badgeClass(row.status)">{{ row.status }}</span>
            </template>
            <template v-else>{{ row[column] || '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-if="row.status === '待巡查'"
              class="link"
              type="button"
              @click="startInspection(row)"
            >开始巡查</button>
            <template v-if="row.status === '巡查中'">
              <button class="link" type="button" @click="openRecord(row)">填写记录</button>
              <button class="link" type="button" @click="openReview(row)">复核</button>
            </template>
            <button class="link" type="button" @click="viewDetail(row)">查看详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的管网巡查记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条管网巡查记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记巡查 -->
    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal">
        <h3 class="modal-title">登记管网巡查</h3>
        <p class="modal-tip">编号唯一，登记后只追加新记录，不会覆盖任何历史巡查。</p>
        <div class="form-grid">
          <label v-for="field in requiredFields" :key="field" class="field">
            <span>{{ field }}<em>*</em></span>
            <input
              v-model="createForm[field]"
              :type="field === '巡查日期' ? 'date' : 'text'"
              :placeholder="`请输入${field}`"
            />
          </label>
        </div>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="createBusy" @click="submitCreate">
            {{ createBusy ? '提交中…' : '提交登记' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 填写巡查记录 -->
    <div v-if="recordVisible" class="modal-mask" @click.self="recordVisible = false">
      <div class="modal">
        <h3 class="modal-title">填写巡查记录 · {{ recordForm['巡查编号'] }}</h3>
        <p class="modal-tip">
          仅保存到巡查编号 {{ recordForm['巡查编号'] }} 这一条记录上；管线状况为空不允许提交。
        </p>
        <div class="form-grid">
          <label class="field field-wide">
            <span>管线状况<em>*</em></span>
            <textarea v-model="recordForm['管线状况']" rows="3" placeholder="必填：描述本次巡查的管线状况"></textarea>
          </label>
          <label class="field field-wide">
            <span>井盖状况</span>
            <textarea v-model="recordForm['井盖状况']" rows="2" placeholder="如有井盖缺失、沉降等情况在此登记"></textarea>
          </label>
          <label class="field field-wide">
            <span>异常描述</span>
            <textarea v-model="recordForm['异常描述']" rows="2" placeholder="发现的异常点位与现象"></textarea>
          </label>
        </div>
        <p v-if="recordError" class="error-text">{{ recordError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="recordVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="recordBusy" @click="submitRecord">
            {{ recordBusy ? '提交中…' : '保存记录' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 复核弹窗 -->
    <div v-if="reviewVisible" class="modal-mask" @click.self="reviewVisible = false">
      <div class="modal">
        <h3 class="modal-title">复核巡查记录 · {{ reviewRow['巡查编号'] }}</h3>
        <dl class="detail-list">
          <div><dt>巡查路段</dt><dd>{{ reviewRow['巡查路段'] }}</dd></div>
          <div><dt>巡查人员</dt><dd>{{ reviewRow['巡查人员'] }}</dd></div>
          <div><dt>巡查日期</dt><dd>{{ reviewRow['巡查日期'] }}</dd></div>
          <div><dt>当前进度</dt><dd><span class="badge" :class="badgeClass(reviewRow.status)">{{ reviewRow.status }}</span></dd></div>
          <div class="detail-wide"><dt>管线状况</dt><dd>{{ reviewRow['管线状况'] || '—' }}</dd></div>
          <div class="detail-wide"><dt>井盖状况</dt><dd>{{ reviewRow['井盖状况'] || '—' }}</dd></div>
          <div class="detail-wide">
            <dt>异常描述</dt>
            <dd>
              <textarea v-model="reviewRow['异常描述']" rows="2" :readonly="reviewRow.status === '已复核'"></textarea>
              <small class="modal-tip">复核通过后异常描述锁定留档，之后不能再修改。</small>
            </dd>
          </div>
        </dl>
        <p v-if="reviewError" class="error-text">{{ reviewError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="reviewVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="reviewBusy" @click="submitReview">
            {{ reviewBusy ? '提交中…' : '复核通过' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 批量补录 -->
    <div v-if="backfillVisible" class="modal-mask modal-wide-mask" @click.self="backfillVisible = false">
      <div class="modal modal-wide">
        <h3 class="modal-title">批量补录管网巡查</h3>
        <p class="modal-tip">
          逐条校验、逐条追加；失败的条目会保留在列表里并注明原因，改完后只重试剩余失败条目即可。
        </p>
        <div v-for="(draft, index) in backfillDrafts" :key="draft.key" class="backfill-row">
          <input v-model="draft['巡查编号']" placeholder="巡查编号*" />
          <input v-model="draft['巡查路段']" placeholder="巡查路段*" />
          <input v-model="draft['巡查人员']" placeholder="巡查人员*" />
          <input v-model="draft['巡查日期']" type="date" />
          <input v-model="draft['管线状况']" placeholder="管线状况（有则进巡查中）" />
          <button class="link danger" type="button" @click="removeDraft(index)">移除</button>
          <small v-if="draft.error" class="error-text backfill-error">{{ draft.error }}</small>
        </div>
        <button class="btn ghost" type="button" @click="addDraft">+ 增加一条</button>
        <p v-if="backfillError" class="error-text">{{ backfillError }}</p>
        <p v-if="backfillMessage" class="success-text">{{ backfillMessage }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="backfillVisible = false">关闭</button>
          <button class="btn primary" type="button" :disabled="backfillBusy" @click="submitBackfill">
            {{ backfillBusy ? '补录中…' : '补录并重试失败项' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string> & { id: number; status: string }

type ActionResponse = {
  ok: boolean
  message: string
  entry?: Row
  blocked?: string[]
}

const ENDPOINT = '/api/pipe'
const router = useRouter()

const columns = ['巡查编号', '巡查路段', '巡查人员', '巡查日期', '管线状况', '井盖状况', '异常描述', '巡查状态']
const statuses = ['待巡查', '巡查中', '已复核']
const requiredFields = ['巡查编号', '巡查路段', '巡查人员', '巡查日期']
const emptyForm = (): Record<string, string> => ({
  巡查编号: '',
  巡查路段: '',
  巡查人员: '',
  巡查日期: '',
})

const rows = ref<Row[]>([])
const total = ref(0)
const stageCounts = ref<Record<string, number>>({})
const errorMessage = ref('')
const filters = ref({ keyword: '', road: '', inspector: '', status: '' })

const stats = computed(() => [
  { key: '待巡查', label: '待巡查路段', value: stageCounts.value['待巡查'] ?? 0 },
  { key: '巡查中', label: '巡查中路段', value: stageCounts.value['巡查中'] ?? 0 },
  { key: '已复核', label: '已复核路段', value: stageCounts.value['已复核'] ?? 0 },
])

function badgeClass(status: string) {
  return {
    待巡查: 'badge-pending',
    巡查中: 'badge-doing',
    已复核: 'badge-done',
  }[status] ?? ''
}

function resetFilters() {
  filters.value = { keyword: '', road: '', inspector: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) query.set(key, value)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('管网巡查列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stageCounts.value = payload.stage_counts ?? {}
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '管网巡查列表读取失败'
  }
}

// ---------- 开始巡查 ----------

async function startInspection(row: Row) {
  errorMessage.value = ''
  try {
    const result = await postAction(row.id, { action: '开始巡查' })
    if (!result.ok) throw new Error(result.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

function viewDetail(row: Row) {
  void router.push(`/pipe/${row.id}`)
}

// ---------- 登记 ----------

const createVisible = ref(false)
const createBusy = ref(false)
const createError = ref('')
const createForm = ref<Record<string, string>>(emptyForm())

function openCreate() {
  createForm.value = emptyForm()
  createError.value = ''
  createVisible.value = true
}

async function submitCreate() {
  createBusy.value = true
  createError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const result = (await response.json()) as ActionResponse
    if (!response.ok || !result.ok) {
      // 失败不关弹窗、不清表单，可直接修改后重试这一条
      createError.value = result.message || '登记失败，请检查填写内容'
      return
    }
    createVisible.value = false
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '登记请求失败'
  } finally {
    createBusy.value = false
  }
}

// ---------- 填写记录 ----------

const recordVisible = ref(false)
const recordBusy = ref(false)
const recordError = ref('')
const recordForm = ref<Record<string, string>>({ id: '' } as Record<string, string>)

async function openRecord(row: Row) {
  recordError.value = ''
  recordVisible.value = true
  recordBusy.value = true
  recordForm.value = { id: String(row.id), 巡查编号: row['巡查编号'], 管线状况: '', 井盖状况: '', 异常描述: '' }
  try {
    // 每次打开都按 id 重新拉取，避免弹窗残留上一条编号的路段/人员/日期造成串号
    const fresh = await fetchEntry(row.id)
    recordForm.value = {
      id: String(fresh.id),
      巡查编号: fresh['巡查编号'],
      管线状况: fresh['管线状况'] ?? '',
      井盖状况: fresh['井盖状况'] ?? '',
      异常描述: fresh['异常描述'] ?? '',
    }
  } catch (error) {
    recordError.value = error instanceof Error ? error.message : '巡查记录读取失败'
  } finally {
    recordBusy.value = false
  }
}

async function submitRecord() {
  recordBusy.value = true
  recordError.value = ''
  try {
    const result = await postAction(Number(recordForm.value.id), {
      action: '填写记录',
      管线状况: recordForm.value['管线状况'],
      井盖状况: recordForm.value['井盖状况'],
      异常描述: recordForm.value['异常描述'],
    })
    if (!result.ok) {
      const codes = result.blocked?.length ? `（被阻断：${result.blocked.join('、')}）` : ''
      recordError.value = `${result.message}${codes}`
      return
    }
    recordVisible.value = false
    await reload()
  } catch (error) {
    recordError.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    recordBusy.value = false
  }
}

// ---------- 复核 ----------

const reviewVisible = ref(false)
const reviewBusy = ref(false)
const reviewError = ref('')
const reviewRow = ref<Row>({} as Row)

async function openReview(row: Row) {
  reviewError.value = ''
  reviewVisible.value = true
  reviewBusy.value = true
  try {
    reviewRow.value = await fetchEntry(row.id)
    if (reviewRow.value.status === '已复核') {
      reviewError.value = `巡查编号 ${reviewRow.value['巡查编号']} 已复核，异常描述已锁定，不能再修改`
    }
  } catch (error) {
    reviewError.value = error instanceof Error ? error.message : '巡查记录读取失败'
  } finally {
    reviewBusy.value = false
  }
}

async function submitReview() {
  reviewBusy.value = true
  reviewError.value = ''
  try {
    // 复核时不回传异常描述：已填写的异常描述原样保留，复核后锁定
    const result = await postAction(Number(reviewRow.value.id), { action: '复核' })
    if (!result.ok) {
      reviewError.value = result.message
      return
    }
    reviewVisible.value = false
    await reload()
  } catch (error) {
    reviewError.value = error instanceof Error ? error.message : '复核失败'
  } finally {
    reviewBusy.value = false
  }
}

// ---------- 批量补录 ----------

type Draft = { key: number; error?: string; [field: string]: string | number | undefined }

const backfillVisible = ref(false)
const backfillBusy = ref(false)
const backfillError = ref('')
const backfillMessage = ref('')
const backfillDrafts = ref<Draft[]>([])
let draftSeq = 0

function makeDraft(): Draft {
  draftSeq += 1
  return { key: draftSeq, ...emptyForm(), 管线状况: '', error: '' }
}

function openBackfill() {
  backfillDrafts.value = [makeDraft()]
  backfillError.value = ''
  backfillMessage.value = ''
  backfillVisible.value = true
}

function addDraft() {
  backfillDrafts.value.push(makeDraft())
}

function removeDraft(index: number) {
  backfillDrafts.value.splice(index, 1)
}

async function submitBackfill() {
  backfillBusy.value = true
  backfillError.value = ''
  backfillMessage.value = ''
  const backfillFields = ['巡查编号', '巡查路段', '巡查人员', '巡查日期', '管线状况']
  const entries = backfillDrafts.value.map((draft) =>
    Object.fromEntries(backfillFields.map((field) => [field, String(draft[field] ?? '')]))
  )
  try {
    const response = await request(`${ENDPOINT}/backfill`, {
      method: 'POST',
      body: JSON.stringify({ entries }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '补录请求失败')
    // 按提交下标对应失败原因；成功的移除，失败的原样保留 —— 下一次提交只重试这些失败条目
    const failures = new Map<number, string>(
      (result.blocked ?? []).map((item: { index: number; 原因: string }) => [item.index, item['原因']])
    )
    backfillDrafts.value = backfillDrafts.value.filter((draft, index) => {
      const reason = failures.get(index)
      draft.error = reason ?? ''
      return reason !== undefined
    })
    backfillMessage.value = result.message
    await reload()
  } catch (error) {
    backfillError.value = error instanceof Error ? error.message : '补录请求失败'
  } finally {
    backfillBusy.value = false
  }
}

// ---------- 通用请求 ----------

async function fetchEntry(id: number): Promise<Row> {
  const response = await request(`${ENDPOINT}/${id}`)
  if (!response.ok) throw new Error('巡查记录读取失败或已归档')
  return (await response.json()) as Row
}

async function postAction(id: number, values: Record<string, string>): Promise<ActionResponse> {
  const response = await request(`${ENDPOINT}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action: values.action, values }),
  })
  if (!response.ok) {
    const detail = (await response.json().catch(() => null))?.detail
    throw new Error(detail || '管网巡查动作未生效，请稍后重试')
  }
  return (await response.json()) as ActionResponse
}

onMounted(reload)
</script>
