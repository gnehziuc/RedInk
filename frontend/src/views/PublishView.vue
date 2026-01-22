<template>
  <div class="publish-view">
    <div class="page-header">
      <h1>发布到小红书</h1>
      <p class="subtitle">将生成的图文内容发布到小红书平台</p>
    </div>
    
    <div class="publish-container">
      <!-- 左侧：发布表单 -->
      <div class="publish-form-section">
        <div class="form-card">
          <!-- 账号选择 -->
          <div class="form-group">
            <label class="form-label">选择账号</label>
            <select v-model="form.accountId" class="form-select" :disabled="isPublishing">
              <option value="">请选择小红书账号</option>
              <option 
                v-for="account in xhsAccounts" 
                :key="account.id" 
                :value="account.id"
                :disabled="account.status !== '正常'"
              >
                {{ account.name }} {{ account.status !== '正常' ? '(已失效)' : '' }}
              </option>
            </select>
            <p v-if="xhsAccounts.length === 0" class="form-hint warning">
              暂无小红书账号，请先在 <router-link to="/account-management">账号管理</router-link> 中添加
            </p>
          </div>
          
          <!-- 标题输入 -->
          <div class="form-group">
            <label class="form-label">标题 <span class="char-count">{{ form.title.length }}/20</span></label>
            <input 
              v-model="form.title" 
              type="text" 
              class="form-input" 
              placeholder="填写标题会有更多赞哦～"
              maxlength="20"
              :disabled="isPublishing"
            />
          </div>
          
          <!-- 正文内容 -->
          <div class="form-group">
            <label class="form-label">正文内容 <span class="char-count">{{ form.content.length }}/1000</span></label>
            <textarea 
              v-model="form.content" 
              class="form-textarea" 
              placeholder="输入笔记正文..."
              maxlength="1000"
              rows="6"
              :disabled="isPublishing"
            ></textarea>
          </div>
          
          <!-- 话题标签 -->
          <div class="form-group">
            <label class="form-label">话题标签</label>
            <div class="tags-input-container">
              <div class="tags-list">
                <span v-for="(tag, index) in form.tags" :key="index" class="tag-item">
                  #{{ tag }}
                  <button type="button" class="tag-remove" @click="removeTag(index)" :disabled="isPublishing">×</button>
                </span>
              </div>
              <input 
                v-model="newTag" 
                type="text" 
                class="tag-input" 
                placeholder="输入话题后按回车添加"
                @keydown.enter.prevent="addTag"
                :disabled="isPublishing"
              />
            </div>
          </div>
          
          <!-- 发布按钮 -->
          <div class="form-actions">
            <button 
              class="btn btn-primary btn-large" 
              @click="handlePublish"
              :disabled="!canPublish || isPublishing"
            >
              <span v-if="isPublishing" class="loading-icon">⟳</span>
              {{ isPublishing ? '发布中...' : '立即发布' }}
            </button>
          </div>
        </div>
      </div>
      
      <!-- 右侧：图片预览 -->
      <div class="preview-section">
        <div class="preview-card">
          <h3 class="preview-title">图片预览</h3>
          
          <div v-if="form.imagePaths.length > 0" class="image-grid">
            <div v-for="(path, index) in form.imagePaths" :key="index" class="image-item">
              <img :src="getImageUrl(path)" :alt="`图片 ${index + 1}`" />
              <button type="button" class="image-remove" @click="removeImage(index)" :disabled="isPublishing">×</button>
              <span class="image-index">{{ index + 1 }}</span>
            </div>
          </div>
          
          <div v-else class="empty-images">
            <p>暂无图片</p>
            <p class="hint">请从历史记录中选择要发布的图片</p>
          </div>
          
          <!-- 从历史记录添加图片 -->
          <div class="add-images-section">
            <button class="btn btn-secondary" @click="showHistoryPicker = true" :disabled="isPublishing">
              + 从历史记录添加图片
            </button>
          </div>
        </div>
        
        <!-- 发布状态 -->
        <div v-if="publishTask" class="status-card">
          <h3 class="status-title">发布状态</h3>
          <div :class="['status-badge', `status-${publishTask.status}`]">
            {{ statusText }}
          </div>
          <p class="status-message">{{ publishTask.message }}</p>
        </div>
      </div>
    </div>
    
    <!-- 历史记录选择弹窗 -->
    <div v-if="showHistoryPicker" class="dialog-overlay" @click.self="showHistoryPicker = false">
      <div class="dialog dialog-large">
        <div class="dialog-header">
          <h3>选择图片</h3>
          <button class="close-btn" @click="showHistoryPicker = false">×</button>
        </div>
        <div class="dialog-body">
          <div v-if="historyRecords.length > 0" class="history-grid">
            <div 
              v-for="record in historyRecords" 
              :key="record.id" 
              class="history-item"
              @click="selectHistoryRecord(record)"
            >
              <img v-if="record.coverImage" :src="record.coverImage" alt="封面" />
              <div class="history-info">
                <p class="history-title">{{ record.title || '未命名' }}</p>
                <p class="history-date">{{ formatDate(record.createdAt) }}</p>
              </div>
            </div>
          </div>
          <div v-else class="empty-history">
            <p>暂无历史记录</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAccountStore } from '@/stores/account'
import { getAccounts, type Account } from '@/api/account'
import { publishXhsImage, getPublishStatus, type PublishTask } from '@/api/publish'
import axios from 'axios'

const accountStore = useAccountStore()

// 表单数据
const form = ref({
  accountId: '' as number | '',
  title: '',
  content: '',
  imagePaths: [] as string[],
  tags: [] as string[]
})

// 状态
const newTag = ref('')
const isPublishing = ref(false)
const showHistoryPicker = ref(false)
const publishTask = ref<PublishTask | null>(null)
const historyRecords = ref<any[]>([])

// 小红书账号列表
const xhsAccounts = computed(() => {
  return accountStore.accounts.filter(acc => acc.platform === '小红书')
})

// 是否可以发布
const canPublish = computed(() => {
  return form.value.accountId && 
         form.value.title && 
         form.value.imagePaths.length > 0
})

// 发布状态文本
const statusText = computed(() => {
  const statusMap: Record<string, string> = {
    pending: '等待中',
    running: '发布中',
    success: '发布成功',
    failed: '发布失败'
  }
  return statusMap[publishTask.value?.status || ''] || '未知'
})

// 获取图片 URL
function getImageUrl(path: string): string {
  // 如果是相对路径，转换为完整 URL
  if (path.startsWith('/api/')) {
    return path
  }
  return `/api/images/${encodeURIComponent(path)}`
}

// 添加标签
function addTag() {
  const tag = newTag.value.trim().replace(/^#/, '')
  if (tag && !form.value.tags.includes(tag)) {
    form.value.tags.push(tag)
  }
  newTag.value = ''
}

// 移除标签
function removeTag(index: number) {
  form.value.tags.splice(index, 1)
}

// 移除图片
function removeImage(index: number) {
  form.value.imagePaths.splice(index, 1)
}

// 格式化日期
function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

// 从历史记录选择
function selectHistoryRecord(record: any) {
  // 添加该记录的所有图片
  if (record.images && record.images.length > 0) {
    form.value.imagePaths = [...form.value.imagePaths, ...record.images]
  }
  // 填充标题和内容
  if (!form.value.title && record.title) {
    form.value.title = record.title.substring(0, 20)
  }
  if (!form.value.content && record.content) {
    form.value.content = record.content.substring(0, 1000)
  }
  showHistoryPicker.value = false
}

// 获取历史记录
async function fetchHistoryRecords() {
  try {
    const response = await axios.get('/api/history')
    if (response.data.code === 200) {
      historyRecords.value = response.data.data || []
    }
  } catch (error) {
    console.error('获取历史记录失败:', error)
  }
}

// 发布
async function handlePublish() {
  if (!canPublish.value || isPublishing.value) return
  
  isPublishing.value = true
  publishTask.value = null
  
  try {
    const result = await publishXhsImage({
      account_id: form.value.accountId as number,
      title: form.value.title,
      content: form.value.content,
      image_paths: form.value.imagePaths,
      tags: form.value.tags
    })
    
    if (result.code === 200 && result.data) {
      // 开始轮询任务状态
      pollTaskStatus(result.data.task_id)
    } else {
      alert(result.msg || '创建发布任务失败')
      isPublishing.value = false
    }
  } catch (error) {
    console.error('发布失败:', error)
    alert('发布失败，请稍后重试')
    isPublishing.value = false
  }
}

// 轮询任务状态
async function pollTaskStatus(taskId: string) {
  const maxAttempts = 60  // 最多轮询60次，每次2秒
  let attempts = 0
  
  const poll = async () => {
    try {
      const result = await getPublishStatus(taskId)
      if (result.code === 200 && result.data) {
        publishTask.value = result.data
        
        if (result.data.status === 'success' || result.data.status === 'failed') {
          isPublishing.value = false
          return
        }
        
        attempts++
        if (attempts < maxAttempts) {
          setTimeout(poll, 2000)
        } else {
          isPublishing.value = false
        }
      }
    } catch (error) {
      console.error('获取任务状态失败:', error)
      isPublishing.value = false
    }
  }
  
  poll()
}

// 获取账号列表
async function fetchAccounts() {
  try {
    const res = await getAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
    }
  } catch (error) {
    console.error('获取账号失败:', error)
  }
}

onMounted(() => {
  fetchAccounts()
  fetchHistoryRecords()
})
</script>

<style scoped>
.publish-view {
  padding: 32px 40px;
  width: 100%;
  box-sizing: border-box;
  min-height: calc(100vh - 100px);
}

.page-header {
  margin-bottom: 32px;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: var(--text-primary, #1a1a1a);
}

.subtitle {
  color: var(--text-secondary, #666);
  margin: 0;
  font-size: 15px;
}

.publish-container {
  display: grid;
  grid-template-columns: 1fr 480px;
  gap: 32px;
  min-height: 600px;
}

.form-card,
.preview-card,
.status-card {
  background: var(--bg-card, #fff);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.form-group {
  margin-bottom: 28px;
}

.form-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-primary, #1a1a1a);
  font-size: 15px;
}

.char-count {
  font-size: 13px;
  color: var(--text-secondary, #999);
  font-weight: normal;
}

.form-select,
.form-input,
.form-textarea {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 10px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.form-select:focus,
.form-input:focus,
.form-textarea:focus {
  border-color: var(--primary, #e74c3c);
  box-shadow: 0 0 0 3px rgba(231, 76, 60, 0.1);
}

.form-textarea {
  resize: vertical;
  min-height: 200px;
  line-height: 1.6;
}

.form-hint {
  font-size: 13px;
  color: var(--text-secondary, #666);
  margin-top: 8px;
}

.form-hint.warning {
  color: #f39c12;
}

.form-hint a {
  color: var(--primary, #e74c3c);
  text-decoration: none;
}

/* Tags */
.tags-input-container {
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 10px;
  padding: 12px 16px;
  min-height: 60px;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  background: #fee;
  color: #ff2442;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.tag-remove {
  margin-left: 8px;
  background: none;
  border: none;
  color: #ff2442;
  cursor: pointer;
  font-size: 16px;
  padding: 0;
}

.tag-input {
  width: 100%;
  border: none;
  outline: none;
  font-size: 15px;
  padding: 6px 0;
}

/* Buttons */
.btn {
  padding: 12px 24px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, var(--primary, #e74c3c) 0%, #ff6b6b 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(231, 76, 60, 0.3);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%);
  box-shadow: 0 6px 16px rgba(231, 76, 60, 0.4);
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--bg-hover, #f5f5f5);
  color: var(--text-primary, #1a1a1a);
  border: 1px solid var(--border-color, #e5e5e5);
}

.btn-secondary:hover {
  background: #eee;
}

.btn-large {
  width: 100%;
  padding: 16px 24px;
  font-size: 17px;
}

.form-actions {
  margin-top: 32px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.loading-icon {
  display: inline-block;
  animation: spin 1s linear infinite;
  margin-right: 8px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Preview */
.preview-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.preview-title,
.status-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 20px 0;
  color: var(--text-primary, #1a1a1a);
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.image-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s;
}

.image-item:hover img {
  transform: scale(1.05);
}

.image-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border: none;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-index {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
}

.empty-images {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary, #666);
  background: var(--bg-hover, #f9f9f9);
  border-radius: 12px;
  border: 2px dashed var(--border-color, #e5e5e5);
}

.empty-images p {
  margin: 0;
  font-size: 16px;
}

.empty-images .hint {
  font-size: 14px;
  margin-top: 12px;
  color: var(--text-secondary, #999);
}

.add-images-section {
  margin-top: 20px;
}

.add-images-section .btn {
  width: 100%;
}

/* Status */
.status-card {
  margin-top: 16px;
}

.status-badge {
  display: inline-block;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 14px;
  margin-bottom: 12px;
}

.status-pending { background: #e3f2fd; color: #1565c0; }
.status-running { background: #fff3e0; color: #ef6c00; }
.status-success { background: #e8f5e9; color: #2e7d32; }
.status-failed { background: #ffebee; color: #c62828; }

.status-message {
  color: var(--text-secondary, #666);
  font-size: 14px;
  margin: 0;
}

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: white;
  border-radius: 12px;
  width: 600px;
  max-width: 90vw;
  max-height: 80vh;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
}

.dialog-large {
  width: 800px;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
}

.dialog-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  cursor: pointer;
  border-radius: 6px;
}

.dialog-body {
  padding: 24px;
  max-height: 60vh;
  overflow-y: auto;
}

.history-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.history-item {
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  border-color: var(--primary, #e74c3c);
  transform: translateY(-2px);
}

.history-item img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
}

.history-info {
  padding: 12px;
}

.history-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-date {
  font-size: 12px;
  color: var(--text-secondary, #999);
  margin: 0;
}

.empty-history {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary, #666);
}

/* Responsive */
@media (max-width: 900px) {
  .publish-container {
    grid-template-columns: 1fr;
  }
}
</style>
