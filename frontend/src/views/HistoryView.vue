<template>
  <div class="container" style="max-width: 1200px;">

    <!-- Header Area -->
    <div class="page-header">
      <div>
        <h1 class="page-title">我的创作</h1>
      </div>
      <div style="display: flex; gap: 10px;">
        <!-- 批量发布按钮 -->
        <button
          v-if="!isSelectMode"
          class="btn"
          @click="enterSelectMode"
          style="border: 1px solid var(--border-color);"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
          批量发布
        </button>
        <!-- 选择模式操作栏 -->
        <template v-else>
          <span class="select-count">已选 {{ selectedRecords.size }} 项</span>
          <button class="btn btn-primary" @click="openPublishModal" :disabled="selectedRecords.size === 0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px;"><path d="M22 2L11 13"></path><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            发布 ({{ selectedRecords.size }})
          </button>
          <button class="btn" @click="exitSelectMode" style="border: 1px solid var(--border-color);">
            取消
          </button>
        </template>
        <button
          class="btn"
          @click="handleScanAll"
          :disabled="isScanning"
          style="border: 1px solid var(--border-color);"
        >
          <svg v-if="!isScanning" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
          <div v-else class="spinner-small" style="margin-right: 6px;"></div>
          {{ isScanning ? '同步中...' : '同步历史' }}
        </button>
        <button class="btn btn-primary" @click="router.push('/')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          新建图文
        </button>
      </div>
    </div>

    <!-- Stats Overview -->
    <StatsOverview v-if="stats" :stats="stats" />

    <!-- Toolbar: Tabs & Search -->
    <div class="toolbar-wrapper">
      <div class="tabs-container" style="margin-bottom: 0; border-bottom: none;">
        <div
          class="tab-item"
          :class="{ active: currentTab === 'all' }"
          @click="switchTab('all')"
        >
          全部
        </div>
        <div
          class="tab-item"
          :class="{ active: currentTab === 'completed' }"
          @click="switchTab('completed')"
        >
          已完成
        </div>
        <div
          class="tab-item"
          :class="{ active: currentTab === 'draft' }"
          @click="switchTab('draft')"
        >
          草稿箱
        </div>
      </div>

      <div class="search-mini">
        <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="搜索标题..."
          @keyup.enter="handleSearch"
        />
      </div>
    </div>

    <!-- Content Area -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else-if="records.length === 0" class="empty-state-large">
      <div class="empty-img">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
      </div>
      <h3>暂无相关记录</h3>
      <p class="empty-tips">去创建一个新的作品吧</p>
    </div>

    <div v-else class="gallery-grid">
      <GalleryCard
        v-for="record in records"
        :key="record.id"
        :record="record"
        :selectable="isSelectMode"
        :selected="selectedRecords.has(record.id)"
        @preview="viewImages"
        @edit="loadRecord"
        @delete="confirmDelete"
        @select="toggleSelect"
        @publish="openSinglePublishModal"
      />
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination-wrapper">
       <button class="page-btn" :disabled="currentPage === 1" @click="changePage(currentPage - 1)">Previous</button>
       <span class="page-indicator">{{ currentPage }} / {{ totalPages }}</span>
       <button class="page-btn" :disabled="currentPage === totalPages" @click="changePage(currentPage + 1)">Next</button>
    </div>

    <!-- 内容预览模态框 (小红书风格) -->
    <ContentPreviewModal
      v-if="viewingRecord"
      :visible="!!viewingRecord"
      :record="viewingRecord"
      :regeneratingImages="regeneratingImages"
      @close="closeGallery"
      @regenerate="regenerateHistoryImage"
      @downloadAll="downloadAllImages"
      @download="downloadImage"
    />

    <!-- 大纲查看模态框 -->
    <OutlineModal
      v-if="showOutlineModal && viewingRecord"
      :visible="showOutlineModal"
      :pages="viewingRecord.outline.pages"
      @close="showOutlineModal = false"
    />

    <!-- 发布弹窗 -->
    <div v-if="showPublishModal" class="modal-overlay" @click="showPublishModal = false">
      <div class="publish-modal" @click.stop>
        <h3>发布到小红书</h3>
        <p class="modal-desc">
          {{ singlePublishRecord ? `将「${singlePublishRecord.title.slice(0, 20)}」发布到小红书` : `将 ${selectedRecords.size} 条笔记发布到小红书` }}
        </p>
        
        <div class="form-group">
          <label>选择账号</label>
          <select v-model="selectedAccountId" class="account-select">
            <option value="" disabled>请选择账号</option>
            <option 
              v-for="account in xhsAccounts" 
              :key="account.id" 
              :value="account.id"
              :disabled="account.status === 0"
            >
              {{ account.userName }} {{ account.status === 0 ? '(已失效)' : '' }}
            </option>
          </select>
        </div>

        <div v-if="publishStatus" class="publish-status" :class="publishStatus.type">
          {{ publishStatus.message }}
        </div>

        <div class="modal-actions">
          <button class="btn" @click="showPublishModal = false" :disabled="isPublishing">
            取消
          </button>
          <button 
            class="btn btn-primary" 
            @click="handlePublish"
            :disabled="!selectedAccountId || isPublishing"
          >
            <div v-if="isPublishing" class="spinner-small" style="margin-right: 6px;"></div>
            {{ isPublishing ? '发布中...' : '确认发布' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  getHistoryList,
  getHistoryStats,
  searchHistory,
  deleteHistory,
  getHistory,
  type HistoryRecord,
  regenerateImage as apiRegenerateImage,
  updateHistory,
  scanAllTasks,
  getAccounts,
  publishToXhs,
  getPublishStatus,
  generatePublishContent,
  type Account
} from '../api'
import { useGeneratorStore } from '../stores/generator'

// 引入组件
import StatsOverview from '../components/history/StatsOverview.vue'
import GalleryCard from '../components/history/GalleryCard.vue'
import ImageGalleryModal from '../components/history/ImageGalleryModal.vue'
import ContentPreviewModal from '../components/history/ContentPreviewModal.vue'
import OutlineModal from '../components/history/OutlineModal.vue'

const router = useRouter()
const route = useRoute()
const store = useGeneratorStore()

// 数据状态
const records = ref<HistoryRecord[]>([])
const loading = ref(false)
const stats = ref<any>(null)
const currentTab = ref('all')
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

// 查看器状态
const viewingRecord = ref<any>(null)
const regeneratingImages = ref<Set<number>>(new Set())
const showOutlineModal = ref(false)
const isScanning = ref(false)

// 批量发布状态
const isSelectMode = ref(false)
const selectedRecords = ref<Set<string>>(new Set())
const showPublishModal = ref(false)
const xhsAccounts = ref<Account[]>([])
const selectedAccountId = ref<number | ''>()
const isPublishing = ref(false)
const publishStatus = ref<{ type: 'info' | 'success' | 'error', message: string } | null>(null)

// 单条发布状态
const singlePublishRecord = ref<any>(null)

/**
 * 加载历史记录列表
 */
async function loadData() {
  loading.value = true
  try {
    let statusFilter = currentTab.value === 'all' ? undefined : currentTab.value
    const res = await getHistoryList(currentPage.value, 12, statusFilter)
    if (res.success) {
      records.value = res.records
      totalPages.value = res.total_pages
    }
  } catch(e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

/**
 * 加载统计数据
 */
async function loadStats() {
  try {
    const res = await getHistoryStats()
    if (res.success) stats.value = res
  } catch(e) {}
}

/**
 * 切换标签页
 */
function switchTab(tab: string) {
  currentTab.value = tab
  currentPage.value = 1
  loadData()
}

/**
 * 搜索历史记录
 */
async function handleSearch() {
  if (!searchKeyword.value.trim()) {
    loadData()
    return
  }
  loading.value = true
  try {
    const res = await searchHistory(searchKeyword.value)
    if (res.success) {
      records.value = res.records
      totalPages.value = 1
    }
  } catch(e) {} finally {
    loading.value = false
  }
}

/**
 * 加载记录并跳转到编辑页
 */
async function loadRecord(id: string) {
  const res = await getHistory(id)
  if (res.success && res.record) {
    store.setTopic(res.record.title)
    store.setOutline(res.record.outline.raw, res.record.outline.pages)
    store.setRecordId(res.record.id)
    if (res.record.images.generated.length > 0) {
      store.taskId = res.record.images.task_id
      store.images = res.record.outline.pages.map((page, idx) => {
        const filename = res.record!.images.generated[idx]
        return {
          index: idx,
          url: filename ? `/api/images/${res.record!.images.task_id}/${filename}` : '',
          status: filename ? 'done' : 'error',
          retryable: !filename
        }
      })
    }
    router.push('/outline')
  }
}

/**
 * 查看图片
 */
async function viewImages(id: string) {
  const res = await getHistory(id)
  if (res.success) viewingRecord.value = res.record
}

/**
 * 关闭图片查看器
 */
function closeGallery() {
  viewingRecord.value = null
  showOutlineModal.value = false
}

/**
 * 确认删除
 */
async function confirmDelete(record: any) {
  if(confirm('确定删除吗？')) {
    await deleteHistory(record.id)
    loadData()
    loadStats()
  }
}

/**
 * 切换页码
 */
function changePage(p: number) {
  currentPage.value = p
  loadData()
}

/**
 * 重新生成历史记录中的图片
 */
async function regenerateHistoryImage(index: number) {
  if (!viewingRecord.value || !viewingRecord.value.images.task_id) {
    alert('无法重新生成：缺少任务信息')
    return
  }

  const page = viewingRecord.value.outline.pages[index]
  if (!page) return

  regeneratingImages.value.add(index)

  try {
    const context = {
      fullOutline: viewingRecord.value.outline.raw || '',
      userTopic: viewingRecord.value.title || ''
    }

    const result = await apiRegenerateImage(
      viewingRecord.value.images.task_id,
      page,
      true,
      context
    )

    if (result.success && result.image_url) {
      const filename = result.image_url.split('/').pop()
      viewingRecord.value.images.generated[index] = filename

      // 刷新图片
      const timestamp = Date.now()
      const imgElements = document.querySelectorAll(`img[src*="${viewingRecord.value.images.task_id}/${filename}"]`)
      imgElements.forEach(img => {
        const baseUrl = (img as HTMLImageElement).src.split('?')[0]
        ;(img as HTMLImageElement).src = `${baseUrl}?t=${timestamp}`
      })

      await updateHistory(viewingRecord.value.id, {
        images: {
          task_id: viewingRecord.value.images.task_id,
          generated: viewingRecord.value.images.generated
        }
      })

      regeneratingImages.value.delete(index)
    } else {
      regeneratingImages.value.delete(index)
      alert('重新生成失败: ' + (result.error || '未知错误'))
    }
  } catch (e) {
    regeneratingImages.value.delete(index)
    alert('重新生成失败: ' + String(e))
  }
}

/**
 * 下载单张图片
 */
function downloadImage(filename: string, index: number) {
  if (!viewingRecord.value) return
  const link = document.createElement('a')
  link.href = `/api/images/${viewingRecord.value.images.task_id}/${filename}?thumbnail=false`
  link.download = `page_${index + 1}.png`
  link.click()
}

/**
 * 打包下载所有图片
 */
function downloadAllImages() {
  if (!viewingRecord.value) return
  const link = document.createElement('a')
  link.href = `/api/history/${viewingRecord.value.id}/download`
  link.click()
}

/**
 * 进入选择模式
 */
function enterSelectMode() {
  isSelectMode.value = true
  selectedRecords.value = new Set()
}

/**
 * 退出选择模式
 */
function exitSelectMode() {
  isSelectMode.value = false
  selectedRecords.value = new Set()
}

/**
 * 切换选中状态
 */
function toggleSelect(recordId: string) {
  const newSet = new Set(selectedRecords.value)
  if (newSet.has(recordId)) {
    newSet.delete(recordId)
  } else {
    newSet.add(recordId)
  }
  selectedRecords.value = newSet
}

/**
 * 打开发布弹窗（批量发布）
 */
async function openPublishModal() {
  singlePublishRecord.value = null  // 清空单条发布记录
  showPublishModal.value = true
  publishStatus.value = null
  
  // 加载小红书账号列表
  const res = await getAccounts()
  if (res.code === 200) {
    // 过滤出小红书账号 (type = 1)
    xhsAccounts.value = res.data.filter((acc: any) => acc[1] === 1).map((acc: any) => ({
      id: acc[0],
      type: acc[1],
      filePath: acc[2],
      userName: acc[3],
      status: acc[4]
    }))
  }
}

/**
 * 打开单条发布弹窗
 */
async function openSinglePublishModal(record: any) {
  singlePublishRecord.value = record  // 保存要发布的记录
  showPublishModal.value = true
  publishStatus.value = null
  
  // 加载小红书账号列表
  const res = await getAccounts()
  if (res.code === 200) {
    xhsAccounts.value = res.data.filter((acc: any) => acc[1] === 1).map((acc: any) => ({
      id: acc[0],
      type: acc[1],
      filePath: acc[2],
      userName: acc[3],
      status: acc[4]
    }))
  }
}

/**
 * 执行发布（支持单条和批量发布）
 */
async function handlePublish() {
  if (!selectedAccountId.value) return
  
  isPublishing.value = true
  publishStatus.value = { type: 'info', message: '正在准备发布...' }
  
  let successCount = 0
  let failCount = 0
  
  // 确定要发布的记录列表
  let recordsToPublish: string[] = []
  if (singlePublishRecord.value) {
    // 单条发布模式
    recordsToPublish = [singlePublishRecord.value.id]
  } else {
    // 批量发布模式
    recordsToPublish = Array.from(selectedRecords.value)
  }
  
  for (const recordId of recordsToPublish) {
    const recordRes = await getHistory(recordId)
    if (!recordRes.success || !recordRes.record) {
      failCount++
      continue
    }
    
    const record = recordRes.record
    
    // 获取图片路径
    const imagePaths = record.images.generated
      .filter((img: string) => img)
      .map((img: string) => `history/${record.images.task_id}/${img}`)
    
    if (imagePaths.length === 0) {
      failCount++
      continue
    }
    
    // 获取发布内容：优先使用 AI 生成的发布内容
    let content = ''
    publishStatus.value = { type: 'info', message: `正在为「${record.title.slice(0, 15)}...」生成发布内容...` }
    
    // 检查是否已有存储的发布内容，如果没有则调用 AI 生成
    if (record.outline.publish_content) {
      content = record.outline.publish_content
    } else {
      // 调用 AI 根据大纲生成发布内容
      const publishContentRes = await generatePublishContent(record.outline.raw)
      if (publishContentRes.success && publishContentRes.publish_content) {
        content = publishContentRes.publish_content
      } else {
        // 失败时回退到简单提取大纲内容
        content = record.outline.pages
          .map((p: any) => p.content)
          .filter((c: string) => !c.includes('配图建议'))
          .join('\n\n')
          .replace(/\[(封面|内容|总结)\]/g, '')
          .trim()
      }
    }
    
    publishStatus.value = { type: 'info', message: `正在发布: ${record.title.slice(0, 20)}...` }
    
    const publishRes = await publishToXhs({
      account_id: selectedAccountId.value as number,
      title: record.title.slice(0, 20),
      content: content.slice(0, 1000),
      image_paths: imagePaths,
      tags: []
    })
    
    if (publishRes.code === 200 && publishRes.data?.task_id) {
      // 轮询等待发布完成
      const taskId = publishRes.data.task_id
      let attempts = 0
      const maxAttempts = 60 // 最多等待60秒
      
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        const statusRes = await getPublishStatus(taskId)
        
        if (statusRes.data?.status === 'success') {
          successCount++
          break
        } else if (statusRes.data?.status === 'failed') {
          failCount++
          break
        }
        attempts++
      }
      
      if (attempts >= maxAttempts) {
        failCount++
      }
    } else {
      failCount++
    }
  }
  
  isPublishing.value = false
  
  if (successCount > 0 && failCount === 0) {
    publishStatus.value = { type: 'success', message: `发布完成！成功 ${successCount} 条` }
  } else if (successCount > 0) {
    publishStatus.value = { type: 'info', message: `发布完成：成功 ${successCount} 条，失败 ${failCount} 条` }
  } else {
    publishStatus.value = { type: 'error', message: `发布失败：${failCount} 条` }
  }
  
  // 3秒后关闭弹窗
  setTimeout(() => {
    showPublishModal.value = false
    singlePublishRecord.value = null  // 清空单条发布记录
    if (!singlePublishRecord.value) {
      exitSelectMode()
    }
  }, 3000)
}

/**
 * 扫描所有任务并同步
 */
async function handleScanAll() {
  isScanning.value = true
  try {
    const result = await scanAllTasks()
    if (result.success) {
      let message = `扫描完成！\n`
      message += `- 总任务数: ${result.total_tasks || 0}\n`
      message += `- 同步成功: ${result.synced || 0}\n`
      message += `- 同步失败: ${result.failed || 0}\n`

      if (result.orphan_tasks && result.orphan_tasks.length > 0) {
        message += `- 孤立任务（无记录）: ${result.orphan_tasks.length} 个\n`
      }

      alert(message)
      await loadData()
      await loadStats()
    } else {
      alert('扫描失败: ' + (result.error || '未知错误'))
    }
  } catch (e) {
    console.error('扫描失败:', e)
    alert('扫描失败: ' + String(e))
  } finally {
    isScanning.value = false
  }
}

onMounted(async () => {
  await loadData()
  await loadStats()

  // 检查路由参数，如果有 ID 则自动打开图片查看器
  if (route.params.id) {
    await viewImages(route.params.id as string)
  }

  // 自动执行一次扫描（静默，不显示结果）
  try {
    const result = await scanAllTasks()
    if (result.success && (result.synced || 0) > 0) {
      await loadData()
      await loadStats()
    }
  } catch (e) {
    console.error('自动扫描失败:', e)
  }
})
</script>

<style scoped>
/* Small Spinner */
.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid var(--primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Toolbar */
.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0;
}

.search-mini {
  position: relative;
  width: 240px;
  margin-bottom: 10px;
}

.search-mini input {
  width: 100%;
  padding: 8px 12px 8px 36px;
  border-radius: 100px;
  border: 1px solid var(--border-color);
  font-size: 14px;
  background: white;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.search-mini input:focus {
  border-color: var(--primary);
  outline: none;
  box-shadow: 0 0 0 3px var(--primary-light);
}

.search-mini .icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #ccc;
}

/* Gallery Grid */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

/* Pagination */
.pagination-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 40px;
}

.page-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: white;
  border-radius: 6px;
  cursor: pointer;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Empty State */
.empty-state-large {
  text-align: center;
  padding: 80px 0;
  color: var(--text-sub);
}

.empty-img {
  font-size: 64px;
  opacity: 0.5;
}

.empty-state-large .empty-tips {
  margin-top: 10px;
  color: var(--text-placeholder);
}

/* Selection Mode */
.select-count {
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 14px;
  color: var(--primary, #ff2442);
  font-weight: 500;
}

/* Publish Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.publish-modal {
  background: white;
  border-radius: 12px;
  padding: 24px;
  width: 90%;
  max-width: 400px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.publish-modal h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
}

.modal-desc {
  margin: 0 0 20px 0;
  color: #666;
  font-size: 14px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
}

.account-select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  background: white;
}

.account-select:focus {
  outline: none;
  border-color: var(--primary, #ff2442);
}

.publish-status {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 16px;
}

.publish-status.info {
  background: #e8f4fd;
  color: #1677ff;
}

.publish-status.success {
  background: #f0fff4;
  color: #52c41a;
}

.publish-status.error {
  background: #fff0f0;
  color: #ff4d4f;
}

.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}
</style>
