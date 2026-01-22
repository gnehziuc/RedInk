<template>
  <div class="account-management">
    <div class="page-header">
      <h1>账号管理</h1>
    </div>
    
    <div class="account-tabs">
      <div class="tabs-nav">
        <button 
          v-for="tab in tabs" 
          :key="tab.key"
          :class="['tab-btn', { active: activeTab === tab.key }]"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
      
      <div class="account-list-container">
        <div class="account-search">
          <input
            v-model="searchKeyword"
            type="text"
            placeholder="输入名称或账号搜索"
            class="search-input"
            @input="handleSearch"
          />
          <div class="action-buttons">
            <button class="btn btn-primary" @click="handleAddAccount">添加账号</button>
            <button class="btn btn-info" @click="fetchAccounts" :disabled="accountStore.isRefreshing">
              <span v-if="accountStore.isRefreshing" class="loading-icon">⟳</span>
              <span v-else>刷新</span>
            </button>
          </div>
        </div>
        
        <div v-if="filteredAccounts.length > 0" class="account-list">
          <table class="account-table">
            <thead>
              <tr>
                <th>头像</th>
                <th>名称</th>
                <th>平台</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="account in filteredAccounts" :key="account.id">
                <td>
                  <div class="avatar" :style="{ background: getAvatarColor(account.name) }">
                    {{ account.name.charAt(0) }}
                  </div>
                </td>
                <td>{{ account.name }}</td>
                <td>
                  <span :class="['platform-tag', getPlatformClass(account.platform)]">
                    {{ account.platform }}
                  </span>
                </td>
                <td>
                  <span 
                    :class="['status-tag', getStatusClass(account.status)]"
                    :style="{ cursor: account.status === '异常' ? 'pointer' : 'default' }"
                    @click="handleStatusClick(account)"
                  >
                    <span v-if="account.status === '验证中'" class="loading-icon">⟳</span>
                    {{ account.status }}
                  </span>
                </td>
                <td class="actions">
                  <button class="btn btn-small" @click="handleEdit(account)">编辑</button>
                  <button class="btn btn-small btn-primary" @click="handleDownloadCookie(account)">下载Cookie</button>
                  <button class="btn btn-small btn-info" @click="handleUploadCookie(account)">上传Cookie</button>
                  <button class="btn btn-small btn-danger" @click="handleDelete(account)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <div v-else class="empty-data">
          <p>暂无{{ activeTab === 'all' ? '' : tabs.find(t => t.key === activeTab)?.label }}账号数据</p>
        </div>
      </div>
    </div>
    
    <!-- 添加/编辑账号对话框 -->
    <div v-if="dialogVisible" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog">
        <div class="dialog-header">
          <h3>{{ dialogType === 'add' ? '添加账号' : '编辑账号' }}</h3>
          <button v-if="!sseConnecting" class="close-btn" @click="closeDialog">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-item">
            <label>平台</label>
            <select 
              v-model="accountForm.platform" 
              :disabled="dialogType === 'edit' || sseConnecting"
              class="form-select"
            >
              <option value="">请选择平台</option>
              <option value="快手">快手</option>
              <option value="抖音">抖音</option>
              <option value="视频号">视频号</option>
              <option value="小红书">小红书</option>
            </select>
          </div>
          <div class="form-item">
            <label>名称</label>
            <input 
              v-model="accountForm.name" 
              type="text"
              placeholder="请输入账号名称"
              :disabled="sseConnecting"
              class="form-input"
            />
          </div>
          
          <!-- 二维码显示区域 -->
          <div v-if="sseConnecting" class="qrcode-container">
            <div v-if="qrCodeData && !loginStatus" class="qrcode-wrapper">
              <p class="qrcode-tip">请使用对应平台APP扫描二维码登录</p>
              <img :src="qrCodeData" alt="登录二维码" class="qrcode-image" />
            </div>
            <div v-else-if="!qrCodeData && !loginStatus" class="loading-wrapper">
              <span class="loading-icon large">⟳</span>
              <span>请求中...</span>
            </div>
            <div v-else-if="loginStatus === '200'" class="success-wrapper">
              <span class="success-icon">✓</span>
              <span>添加成功</span>
            </div>
            <div v-else-if="loginStatus === '500'" class="error-wrapper">
              <span class="error-icon">✗</span>
              <span>添加失败，请稍后再试</span>
            </div>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn" @click="closeDialog" :disabled="sseConnecting">取消</button>
          <button 
            class="btn btn-primary" 
            @click="submitAccountForm" 
            :disabled="sseConnecting || !accountForm.platform || !accountForm.name"
          >
            {{ sseConnecting ? '请求中...' : '确认' }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- 确认删除对话框 -->
    <div v-if="deleteDialogVisible" class="dialog-overlay" @click.self="deleteDialogVisible = false">
      <div class="dialog dialog-small">
        <div class="dialog-header">
          <h3>确认删除</h3>
          <button class="close-btn" @click="deleteDialogVisible = false">×</button>
        </div>
        <div class="dialog-body">
          <p>确定要删除账号 <strong>{{ accountToDelete?.name }}</strong> 吗？</p>
        </div>
        <div class="dialog-footer">
          <button class="btn" @click="deleteDialogVisible = false">取消</button>
          <button class="btn btn-danger" @click="confirmDelete">确定删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAccountStore } from '@/stores/account'
import { 
  getAccounts, 
  getValidAccounts, 
  deleteAccount as deleteAccountApi, 
  updateAccount as updateAccountApi,
  getCookieDownloadUrl,
  getLoginSSEUrl,
  uploadCookie,
  type Account
} from '@/api/account'

const accountStore = useAccountStore()

// Tab 配置
const tabs = [
  { key: 'all', label: '全部' },
  { key: 'kuaishou', label: '快手' },
  { key: 'douyin', label: '抖音' },
  { key: 'channels', label: '视频号' },
  { key: 'xiaohongshu', label: '小红书' }
]

const activeTab = ref('all')
const searchKeyword = ref('')

// 对话框状态
const dialogVisible = ref(false)
const dialogType = ref<'add' | 'edit'>('add')
const deleteDialogVisible = ref(false)
const accountToDelete = ref<Account | null>(null)

// 账号表单
const accountForm = ref({
  id: 0,
  name: '',
  platform: '',
  status: '正常'
})

// SSE 登录状态
const sseConnecting = ref(false)
const qrCodeData = ref('')
const loginStatus = ref('')
let eventSource: EventSource | null = null

// 平台类型映射
const platformTypeMap: Record<string, string> = {
  '小红书': '1',
  '视频号': '2',
  '抖音': '3',
  '快手': '4'
}

// 过滤后的账号列表
const filteredAccounts = computed(() => {
  let accounts = accountStore.accounts
  
  // 按平台过滤
  if (activeTab.value !== 'all') {
    const platformMap: Record<string, string> = {
      kuaishou: '快手',
      douyin: '抖音',
      channels: '视频号',
      xiaohongshu: '小红书'
    }
    const platform = platformMap[activeTab.value]
    accounts = accounts.filter(acc => acc.platform === platform)
  }
  
  // 按搜索关键词过滤
  if (searchKeyword.value) {
    accounts = accounts.filter(acc => 
      acc.name.includes(searchKeyword.value)
    )
  }
  
  return accounts
})

// 获取头像颜色
function getAvatarColor(name: string): string {
  const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
  const index = name.charCodeAt(0) % colors.length
  return colors[index]
}

// 获取平台样式类
function getPlatformClass(platform: string): string {
  const classMap: Record<string, string> = {
    '快手': 'platform-kuaishou',
    '抖音': 'platform-douyin',
    '视频号': 'platform-channels',
    '小红书': 'platform-xiaohongshu'
  }
  return classMap[platform] || ''
}

// 获取状态样式类
function getStatusClass(status: string): string {
  if (status === '验证中') return 'status-pending'
  if (status === '正常') return 'status-normal'
  return 'status-error'
}

// 快速获取账号（不验证）- 直接显示数据库中的真实状态
async function fetchAccountsQuick() {
  try {
    const res = await getAccounts()
    if (res.code === 200 && res.data) {
      // 直接设置账号数据，显示数据库中的真实状态
      accountStore.setAccounts(res.data)
    }
  } catch (error) {
    console.error('快速获取账号数据失败:', error)
  }
}

// 获取账号（带验证）
async function fetchAccounts() {
  if (accountStore.isRefreshing) return
  
  accountStore.setRefreshing(true)
  try {
    const res = await getValidAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
      accountStore.markVisited()
    }
  } catch (error) {
    console.error('获取账号数据失败:', error)
  } finally {
    accountStore.setRefreshing(false)
  }
}

// 页面加载 - 直接获取账号显示真实状态
onMounted(() => {
  fetchAccountsQuick()
})

// 搜索处理
function handleSearch() {
  // 搜索由计算属性处理
}

// 添加账号
function handleAddAccount() {
  dialogType.value = 'add'
  accountForm.value = { id: 0, name: '', platform: '', status: '正常' }
  sseConnecting.value = false
  qrCodeData.value = ''
  loginStatus.value = ''
  dialogVisible.value = true
}

// 编辑账号
function handleEdit(account: Account) {
  dialogType.value = 'edit'
  accountForm.value = {
    id: account.id,
    name: account.name,
    platform: account.platform,
    status: account.status
  }
  dialogVisible.value = true
}

// 删除账号
function handleDelete(account: Account) {
  accountToDelete.value = account
  deleteDialogVisible.value = true
}

// 确认删除
async function confirmDelete() {
  if (!accountToDelete.value) return
  
  try {
    const response = await deleteAccountApi(accountToDelete.value.id)
    if (response.code === 200) {
      accountStore.deleteAccount(accountToDelete.value.id)
      deleteDialogVisible.value = false
      accountToDelete.value = null
    }
  } catch (error) {
    console.error('删除账号失败:', error)
  }
}

// 下载 Cookie
function handleDownloadCookie(account: Account) {
  const downloadUrl = getCookieDownloadUrl(account.filePath)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = `${account.name}_cookie.json`
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 上传 Cookie
function handleUploadCookie(account: Account) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  
  input.onchange = async (event) => {
    const file = (event.target as HTMLInputElement).files?.[0]
    if (!file) return
    
    if (!file.name.endsWith('.json')) {
      alert('请选择 JSON 格式的 Cookie 文件')
      return
    }
    
    try {
      const result = await uploadCookie(account.id, account.platform, file)
      if (result.code === 200) {
        alert('Cookie 文件上传成功')
        fetchAccounts()
      } else {
        alert(result.msg || 'Cookie 文件上传失败')
      }
    } catch (error) {
      console.error('上传 Cookie 文件失败:', error)
      alert('Cookie 文件上传失败')
    }
  }
  
  input.click()
}

// 状态点击处理（重新登录）
function handleStatusClick(account: Account) {
  if (account.status === '异常') {
    handleReLogin(account)
  }
}

// 重新登录
function handleReLogin(account: Account) {
  dialogType.value = 'edit'
  accountForm.value = {
    id: account.id,
    name: account.name,
    platform: account.platform,
    status: account.status
  }
  sseConnecting.value = false
  qrCodeData.value = ''
  loginStatus.value = ''
  dialogVisible.value = true
  
  setTimeout(() => {
    connectSSE(account.platform, account.name)
  }, 300)
}

// 关闭 SSE 连接
function closeSSEConnection() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

// 建立 SSE 连接
function connectSSE(platform: string, name: string) {
  closeSSEConnection()
  
  sseConnecting.value = true
  qrCodeData.value = ''
  loginStatus.value = ''
  
  const type = platformTypeMap[platform] || '1'
  const url = getLoginSSEUrl(type, name)
  
  eventSource = new EventSource(url)
  
  eventSource.onmessage = (event) => {
    const data = event.data
    console.log('SSE 消息:', data)
    
    if (!qrCodeData.value && data.length > 100) {
      if (data.startsWith('data:image')) {
        qrCodeData.value = data
      } else {
        qrCodeData.value = `data:image/png;base64,${data}`
      }
    } else if (data === '200' || data === '500') {
      loginStatus.value = data
      
      if (data === '200') {
        setTimeout(() => {
          closeSSEConnection()
          setTimeout(() => {
            dialogVisible.value = false
            sseConnecting.value = false
            fetchAccounts()
          }, 1000)
        }, 1000)
      } else {
        closeSSEConnection()
        setTimeout(() => {
          sseConnecting.value = false
          qrCodeData.value = ''
          loginStatus.value = ''
        }, 2000)
      }
    }
  }
  
  eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error)
    closeSSEConnection()
    sseConnecting.value = false
  }
}

// 提交表单
async function submitAccountForm() {
  if (!accountForm.value.platform || !accountForm.value.name) {
    return
  }
  
  if (dialogType.value === 'add') {
    connectSSE(accountForm.value.platform, accountForm.value.name)
  } else {
    // 编辑模式
    try {
      const platformTypeMapReverse: Record<string, number> = {
        '快手': 4,
        '抖音': 3,
        '视频号': 2,
        '小红书': 1
      }
      
      const res = await updateAccountApi({
        id: accountForm.value.id,
        type: platformTypeMapReverse[accountForm.value.platform] || 1,
        userName: accountForm.value.name
      })
      
      if (res.code === 200) {
        accountStore.updateAccount(accountForm.value.id, {
          name: accountForm.value.name,
          platform: accountForm.value.platform
        })
        dialogVisible.value = false
        fetchAccounts()
      }
    } catch (error) {
      console.error('更新账号失败:', error)
    }
  }
}

// 关闭对话框
function closeDialog() {
  if (!sseConnecting.value) {
    dialogVisible.value = false
    closeSSEConnection()
  }
}



// 页面卸载
onBeforeUnmount(() => {
  closeSSEConnection()
})
</script>

<style scoped>
.account-management {
  padding: 24px;
  width: 100%;
  box-sizing: border-box;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 24px 0;
  color: var(--text-primary, #1a1a1a);
}

.account-tabs {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.tabs-nav {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
  padding-bottom: 16px;
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary, #666);
  border-radius: 6px;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: var(--bg-hover, #f5f5f5);
}

.tab-btn.active {
  background: var(--primary, #e74c3c);
  color: white;
}

.account-search {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.search-input {
  width: 300px;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--primary, #e74c3c);
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 10px 16px;
  border: 1px solid var(--border-color, #e5e5e5);
  background: white;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn:hover {
  background: var(--bg-hover, #f5f5f5);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary, #e74c3c);
  color: white;
  border-color: var(--primary, #e74c3c);
}

.btn-primary:hover {
  background: #c0392b;
  border-color: #c0392b;
}

.btn-info {
  background: #3498db;
  color: white;
  border-color: #3498db;
}

.btn-info:hover {
  background: #2980b9;
  border-color: #2980b9;
}

.btn-danger {
  background: #e74c3c;
  color: white;
  border-color: #e74c3c;
}

.btn-danger:hover {
  background: #c0392b;
  border-color: #c0392b;
}

.btn-small {
  padding: 6px 12px;
  font-size: 13px;
}

.account-table {
  width: 100%;
  border-collapse: collapse;
}

.account-table th,
.account-table td {
  padding: 14px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
}

.account-table th {
  font-weight: 500;
  color: var(--text-secondary, #666);
  font-size: 13px;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
}

.platform-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 13px;
}

.platform-kuaishou { background: #ffe8d9; color: #ff6b00; }
.platform-douyin { background: #ffe4e8; color: #fe2c55; }
.platform-channels { background: #e8f5e9; color: #07c160; }
.platform-xiaohongshu { background: #fee; color: #ff2442; }

.status-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 13px;
}

.status-normal { background: #e8f5e9; color: #2e7d32; }
.status-error { background: #ffebee; color: #c62828; }
.status-pending { background: #e3f2fd; color: #1565c0; }

.actions {
  display: flex;
  gap: 8px;
}

.empty-data {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary, #666);
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
  width: 480px;
  max-width: 90vw;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
}

.dialog-small {
  width: 400px;
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
  font-weight: 600;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  cursor: pointer;
  border-radius: 6px;
  color: var(--text-secondary, #666);
}

.close-btn:hover {
  background: var(--bg-hover, #f5f5f5);
}

.dialog-body {
  padding: 24px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color, #e5e5e5);
}

.form-item {
  margin-bottom: 20px;
}

.form-item label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--text-primary, #1a1a1a);
}

.form-select,
.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.form-select:focus,
.form-input:focus {
  border-color: var(--primary, #e74c3c);
}

.form-select:disabled,
.form-input:disabled {
  background: var(--bg-disabled, #f5f5f5);
  cursor: not-allowed;
}

/* QR Code */
.qrcode-container {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 250px;
  justify-content: center;
}

.qrcode-wrapper {
  text-align: center;
}

.qrcode-tip {
  margin-bottom: 16px;
  color: var(--text-secondary, #666);
}

.qrcode-image {
  max-width: 200px;
  max-height: 200px;
  border: 1px solid var(--border-color, #e5e5e5);
  background: #000;
}

.loading-wrapper,
.success-wrapper,
.error-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.loading-icon {
  display: inline-block;
  animation: spin 1s linear infinite;
}

.loading-icon.large {
  font-size: 48px;
}

.success-icon {
  font-size: 48px;
  color: #2e7d32;
}

.error-icon {
  font-size: 48px;
  color: #c62828;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
