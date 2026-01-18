<template>
  <div class="card mcp-config-card">
    <div class="section-header">
      <div>
        <h2 class="section-title">MCP 工具配置</h2>
        <p class="section-desc">集成外部 MCP 服务器提供的工具到 AI Agent</p>
      </div>
      <div class="header-actions">
        <button
          class="btn btn-small btn-outline"
          @click="addServer"
          :disabled="loading"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          添加服务器
        </button>
      </div>
    </div>

    <!-- MCP 启用开关 -->
    <div class="mcp-toggle">
      <label class="toggle-label">
        <input
          type="checkbox"
          :checked="config.enabled"
          @change="handleToggleEnabled"
          :disabled="loading"
        />
        <span class="toggle-switch"></span>
        <span class="toggle-text">
          {{ config.enabled ? '已启用 MCP 工具集成' : '未启用 MCP 工具集成' }}
        </span>
      </label>
      <p class="toggle-desc">
        启用后，AI Agent 可以调用配置的 MCP 服务器提供的工具
      </p>
    </div>

    <!-- 服务器列表 -->
    <div v-if="Object.keys(config.servers).length > 0" class="servers-list">
      <div
        v-for="(server, serverName) in config.servers"
        :key="serverName"
        class="server-item"
      >
        <div class="server-header" @click="toggleServerExpand(serverName as string)">
          <div class="server-info">
            <span class="server-name">{{ serverName }}</span>
            <span class="server-type-badge">{{ getServerTypeLabel(server.type) }}</span>
            <span
              class="server-status"
              :class="{ 'status-enabled': server.enabled, 'status-disabled': !server.enabled }"
            >
              {{ server.enabled ? '已启用' : '已禁用' }}
            </span>
            <span v-if="serverStatus[serverName as string]" class="server-connection">
              <span
                class="connection-dot"
                :class="{ 'connected': serverStatus[serverName as string]?.connected }"
              ></span>
              {{ serverStatus[serverName as string]?.connected ? '已连接' : '未连接' }}
            </span>
          </div>
          <div class="server-actions">
            <button
              class="btn btn-icon"
              @click.stop="testServer(serverName as string)"
              :disabled="testing === serverName"
              title="测试连接"
            >
              <svg v-if="testing !== serverName" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
              <span v-else class="spinner-small"></span>
            </button>
            <button
              class="btn btn-icon"
              @click.stop="editServer(serverName as string)"
              title="编辑"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </button>
            <button
              class="btn btn-icon btn-danger"
              @click.stop="deleteServer(serverName as string)"
              title="删除"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
            <span class="expand-icon">{{ expandedServers.has(serverName as string) ? '▼' : '▶' }}</span>
          </div>
        </div>

        <!-- 展开的工具列表 -->
        <div v-if="expandedServers.has(serverName as string)" class="server-details">
          <div class="server-config-info">
            <!-- stdio 类型显示命令 -->
            <div v-if="server.type !== 'streamableHttp'" class="config-row">
              <span class="config-label">命令:</span>
              <code class="config-value">{{ server.command }} {{ (server.args || []).join(' ') }}</code>
            </div>
            <!-- streamableHttp 类型显示 URL -->
            <div v-else class="config-row">
              <span class="config-label">URL:</span>
              <code class="config-value">{{ server.url }}</code>
            </div>
          </div>

          <!-- 工具列表 -->
          <div v-if="serverTools[serverName as string]?.length > 0" class="tools-section">
            <div class="tools-header">
              可用工具 ({{ serverTools[serverName as string].length }})
            </div>
            <div class="tools-list">
              <div
                v-for="tool in serverTools[serverName as string]"
                :key="tool.name"
                class="tool-item"
              >
                <div class="tool-header" @click="toggleToolExpand(serverName as string, tool.name)">
                  <div class="tool-main">
                    <div class="tool-name">{{ tool.name }}</div>
                    <div class="tool-description">{{ tool.description || '无描述' }}</div>
                  </div>
                  <span class="tool-expand-icon">
                    {{ expandedTools.has(`${serverName}:${tool.name}`) ? '▼' : '▶' }}
                  </span>
                </div>
                <!-- 工具参数详情 -->
                <div v-if="expandedTools.has(`${serverName}:${tool.name}`)" class="tool-params">
                  <div v-if="hasToolParams(tool)" class="params-list">
                    <div class="params-title">调用参数：</div>
                    <div
                      v-for="(param, paramName) in getToolParams(tool)"
                      :key="paramName"
                      class="param-item"
                    >
                      <div class="param-header">
                        <code class="param-name">{{ paramName }}</code>
                        <span class="param-type">{{ param.type || 'string' }}</span>
                        <span
                          class="param-required"
                          :class="{ 'required': isParamRequired(tool, paramName as string) }"
                        >
                          {{ isParamRequired(tool, paramName as string) ? '必填' : '可选' }}
                        </span>
                      </div>
                      <div v-if="param.description" class="param-description">
                        {{ param.description }}
                      </div>
                      <div v-if="param.default !== undefined" class="param-default">
                        默认值: <code>{{ JSON.stringify(param.default) }}</code>
                      </div>
                      <div v-if="param.enum && param.enum.length > 0" class="param-enum">
                        可选值: <code v-for="(val, idx) in param.enum" :key="idx">{{ val }}{{ idx < param.enum.length - 1 ? ', ' : '' }}</code>
                      </div>
                    </div>
                  </div>
                  <div v-else class="no-params">
                    该工具无需输入参数
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="no-tools">
            <p>暂无工具信息，请点击测试按钮获取</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5">
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
        <line x1="8" y1="21" x2="16" y2="21"></line>
        <line x1="12" y1="17" x2="12" y2="21"></line>
      </svg>
      <p>暂未配置 MCP 服务器</p>
      <button class="btn" @click="addServer">添加服务器</button>
    </div>

    <!-- 编辑/添加弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingServer ? '编辑服务器' : '添加服务器' }}</h3>
          <button class="btn btn-icon" @click="closeModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label>服务器名称</label>
            <input
              v-model="form.name"
              type="text"
              placeholder="例如: filesystem, fetch"
              :disabled="!!editingServer"
            />
          </div>

          <div class="form-group">
            <label>传输类型</label>
            <select v-model="form.type" class="form-select">
              <option value="stdio">stdio（本地进程）</option>
              <option value="streamableHttp">Streamable HTTP（远程服务器）</option>
            </select>
          </div>

          <!-- stdio 类型配置 -->
          <template v-if="form.type === 'stdio'">
            <div class="form-group">
              <label>启动命令</label>
              <input
                v-model="form.command"
                type="text"
                placeholder="例如: npx, uvx, python"
              />
            </div>

            <div class="form-group">
              <label>命令参数（每行一个）</label>
              <textarea
                v-model="form.argsText"
                placeholder="例如:&#10;-y&#10;@modelcontextprotocol/server-filesystem&#10;/path/to/dir"
                rows="4"
              ></textarea>
            </div>

            <div class="form-group">
              <label>环境变量（每行一个，格式: KEY=VALUE）</label>
              <textarea
                v-model="form.envText"
                placeholder="例如:&#10;API_KEY=your-key&#10;DEBUG=true"
                rows="3"
              ></textarea>
            </div>
          </template>

          <!-- streamableHttp 类型配置 -->
          <template v-else>
            <div class="form-group">
              <label>服务器 URL（完整端点地址）</label>
              <input
                v-model="form.url"
                type="text"
                placeholder="例如: https://mcp.example.com/sse 或 https://api.example.com/mcp"
              />
            </div>

            <div class="form-group">
              <label>HTTP 请求头（每行一个，格式: Header-Name: value）</label>
              <textarea
                v-model="form.headersText"
                placeholder="例如:&#10;Authorization: Bearer your-token&#10;X-Custom-Header: value"
                rows="3"
              ></textarea>
            </div>
          </template>

          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="form.enabled" />
              <span>启用此服务器</span>
            </label>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeModal">取消</button>
          <button
            class="btn"
            @click="saveServer"
            :disabled="!isFormValid || saving"
          >
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 消息提示 -->
    <div v-if="message" class="message" :class="messageType">
      {{ message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import {
  getMCPConfig,
  updateMCPConfig,
  testMCPConnection,
  getMCPStatus,
  type MCPConfig,
  type MCPTool
} from '../../api'

// 扩展服务器配置类型
interface ExtendedServerConfig {
  type?: string
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
  enabled: boolean
  tools?: MCPTool[]
}

interface ExtendedMCPConfig {
  enabled: boolean
  servers: Record<string, ExtendedServerConfig>
}

// 状态
const loading = ref(false)
const saving = ref(false)
const testing = ref<string | null>(null)
const showModal = ref(false)
const editingServer = ref<string | null>(null)
const message = ref('')
const messageType = ref<'success' | 'error'>('success')

// 配置数据
const config = reactive<ExtendedMCPConfig>({
  enabled: false,
  servers: {}
})

// 服务器状态和工具
const serverStatus = ref<Record<string, { connected: boolean; healthy: boolean; tool_count: number }>>({})
const serverTools = ref<Record<string, MCPTool[]>>({})
const expandedServers = ref<Set<string>>(new Set())
const expandedTools = ref<Set<string>>(new Set())

// 表单数据
const form = reactive({
  name: '',
  type: 'stdio' as 'stdio' | 'streamableHttp',
  command: '',
  argsText: '',
  envText: '',
  url: '',
  headersText: '',
  enabled: true
})

// 表单验证
const isFormValid = computed(() => {
  if (!form.name) return false
  if (form.type === 'stdio') {
    return !!form.command
  } else {
    return !!form.url
  }
})

// 获取服务器类型标签
function getServerTypeLabel(type?: string): string {
  if (type === 'streamableHttp') {
    return 'HTTP'
  }
  return 'stdio'
}

// 加载配置
async function loadConfig() {
  loading.value = true
  try {
    const result = await getMCPConfig()
    if (result.success && result.config) {
      config.enabled = result.config.enabled
      config.servers = result.config.servers as Record<string, ExtendedServerConfig>

      // 从配置中加载已保存的工具列表
      for (const [serverName, serverConfig] of Object.entries(config.servers)) {
        if (serverConfig.tools && serverConfig.tools.length > 0) {
          serverTools.value[serverName] = serverConfig.tools
        }
      }
    }

    // 加载状态
    const statusResult = await getMCPStatus()
    if (statusResult.success && statusResult.status) {
      serverStatus.value = statusResult.status.servers
    }
  } catch (e) {
    showMessage('加载配置失败', 'error')
  } finally {
    loading.value = false
  }
}

// 切换启用状态
async function handleToggleEnabled(event: Event) {
  const target = event.target as HTMLInputElement
  const newEnabled = target.checked

  try {
    const result = await updateMCPConfig({ enabled: newEnabled })
    if (result.success) {
      config.enabled = newEnabled
      showMessage(newEnabled ? 'MCP 工具集成已启用' : 'MCP 工具集成已禁用', 'success')
    } else {
      target.checked = !newEnabled
      showMessage(result.error || '更新失败', 'error')
    }
  } catch (e) {
    target.checked = !newEnabled
    showMessage('更新失败', 'error')
  }
}

// 展开/折叠服务器
function toggleServerExpand(serverName: string) {
  if (expandedServers.value.has(serverName)) {
    expandedServers.value.delete(serverName)
  } else {
    expandedServers.value.add(serverName)
  }
}

// 展开/折叠工具参数
function toggleToolExpand(serverName: string, toolName: string) {
  const key = `${serverName}:${toolName}`
  if (expandedTools.value.has(key)) {
    expandedTools.value.delete(key)
  } else {
    expandedTools.value.add(key)
  }
}

// 检查工具是否有参数
function hasToolParams(tool: MCPTool): boolean {
  const schema = tool.input_schema
  if (!schema || !schema.properties) return false
  return Object.keys(schema.properties).length > 0
}

// 获取工具参数列表
function getToolParams(tool: MCPTool): Record<string, any> {
  return tool.input_schema?.properties || {}
}

// 检查参数是否必填
function isParamRequired(tool: MCPTool, paramName: string): boolean {
  const required = tool.input_schema?.required || []
  return required.includes(paramName)
}

// 测试服务器连接
async function testServer(serverName: string) {
  testing.value = serverName

  try {
    const result = await testMCPConnection(serverName)
    if (result.success) {
      showMessage(result.message || '连接成功', 'success')
      if (result.tools) {
        serverTools.value[serverName] = result.tools
      }
      // 刷新状态
      const statusResult = await getMCPStatus()
      if (statusResult.success && statusResult.status) {
        serverStatus.value = statusResult.status.servers
      }
    } else {
      showMessage(result.error || '连接失败', 'error')
    }
  } catch (e) {
    showMessage('测试失败', 'error')
  } finally {
    testing.value = null
  }
}

// 添加服务器
function addServer() {
  editingServer.value = null
  form.name = ''
  form.type = 'stdio'
  form.command = ''
  form.argsText = ''
  form.envText = ''
  form.url = ''
  form.headersText = ''
  form.enabled = true
  showModal.value = true
}

// 编辑服务器
function editServer(serverName: string) {
  const server = config.servers[serverName]
  if (!server) return

  editingServer.value = serverName
  form.name = serverName
  form.type = (server.type === 'streamableHttp' ? 'streamableHttp' : 'stdio') as 'stdio' | 'streamableHttp'
  form.enabled = server.enabled

  if (form.type === 'stdio') {
    form.command = server.command || ''
    form.argsText = (server.args || []).join('\n')

    // 处理环境变量，过滤掉 _xxx_set 标记
    const envLines: string[] = []
    for (const [key, value] of Object.entries(server.env || {})) {
      if (!key.startsWith('_') && !key.endsWith('_set')) {
        envLines.push(`${key}=${value}`)
      }
    }
    form.envText = envLines.join('\n')
    form.url = ''
    form.headersText = ''
  } else {
    form.url = server.url || ''

    // 处理 headers，过滤掉 _xxx_set 标记
    const headerLines: string[] = []
    for (const [key, value] of Object.entries(server.headers || {})) {
      if (!key.startsWith('_') && !key.endsWith('_set')) {
        headerLines.push(`${key}: ${value}`)
      }
    }
    form.headersText = headerLines.join('\n')
    form.command = ''
    form.argsText = ''
    form.envText = ''
  }

  showModal.value = true
}

// 删除服务器
async function deleteServer(serverName: string) {
  if (!confirm(`确定要删除服务器 "${serverName}" 吗？`)) return

  const newServers = { ...config.servers }
  delete newServers[serverName]

  try {
    const result = await updateMCPConfig({ servers: newServers as any })
    if (result.success) {
      config.servers = newServers
      delete serverTools.value[serverName]
      delete serverStatus.value[serverName]
      expandedServers.value.delete(serverName)
      showMessage('服务器已删除', 'success')
    } else {
      showMessage(result.error || '删除失败', 'error')
    }
  } catch (e) {
    showMessage('删除失败', 'error')
  }
}

// 关闭弹窗
function closeModal() {
  showModal.value = false
  editingServer.value = null
}

// 保存服务器
async function saveServer() {
  if (!isFormValid.value) return

  saving.value = true

  try {
    let serverConfig: ExtendedServerConfig

    if (form.type === 'stdio') {
      // 解析参数
      const args = form.argsText
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)

      // 解析环境变量
      const env: Record<string, string> = {}
      form.envText
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .forEach(line => {
          const idx = line.indexOf('=')
          if (idx > 0) {
            const key = line.substring(0, idx)
            const value = line.substring(idx + 1)
            env[key] = value
          }
        })

      serverConfig = {
        type: 'stdio',
        command: form.command,
        args,
        env,
        enabled: form.enabled
      }
    } else {
      // 解析 headers
      const headers: Record<string, string> = {}
      form.headersText
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .forEach(line => {
          const idx = line.indexOf(':')
          if (idx > 0) {
            const key = line.substring(0, idx).trim()
            const value = line.substring(idx + 1).trim()
            headers[key] = value
          }
        })

      serverConfig = {
        type: 'streamableHttp',
        url: form.url,
        headers,
        enabled: form.enabled
      }
    }

    const newServers = {
      ...config.servers,
      [form.name]: serverConfig
    }

    const result = await updateMCPConfig({ servers: newServers as any })
    if (result.success) {
      config.servers = newServers
      showMessage('服务器已保存', 'success')
      closeModal()
    } else {
      showMessage(result.error || '保存失败', 'error')
    }
  } catch (e) {
    showMessage('保存失败', 'error')
  } finally {
    saving.value = false
  }
}

// 显示消息
function showMessage(msg: string, type: 'success' | 'error') {
  message.value = msg
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 3000)
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.mcp-config-card {
  position: relative;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #1a1a1a;
}

.section-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* MCP 启用开关 */
.mcp-toggle {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  margin-bottom: 20px;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.toggle-label input {
  display: none;
}

.toggle-switch {
  position: relative;
  width: 48px;
  height: 26px;
  background: #ddd;
  border-radius: 13px;
  transition: background 0.3s;
}

.toggle-switch::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: transform 0.3s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.toggle-label input:checked + .toggle-switch {
  background: var(--primary, #ff2442);
}

.toggle-label input:checked + .toggle-switch::after {
  transform: translateX(22px);
}

.toggle-text {
  font-size: 15px;
  font-weight: 500;
  color: #333;
}

.toggle-desc {
  margin: 12px 0 0;
  font-size: 13px;
  color: #666;
  line-height: 1.5;
}

/* 服务器列表 */
.servers-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.server-item {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  overflow: hidden;
}

.server-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fafafa;
  cursor: pointer;
  transition: background 0.2s;
}

.server-header:hover {
  background: #f0f0f0;
}

.server-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.server-name {
  font-weight: 600;
  color: #333;
}

.server-type-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e3f2fd;
  color: #1976d2;
  font-weight: 500;
}

.server-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-enabled {
  background: #e6f7e6;
  color: #2e7d32;
}

.status-disabled {
  background: #f5f5f5;
  color: #666;
}

.server-connection {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
}

.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}

.connection-dot.connected {
  background: #4caf50;
}

.server-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.expand-icon {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}

/* 服务器详情 */
.server-details {
  padding: 16px;
  border-top: 1px solid #e5e5e5;
  background: #fff;
}

.server-config-info {
  margin-bottom: 16px;
}

.config-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
}

.config-label {
  color: #666;
  min-width: 60px;
}

.config-value {
  background: #f5f5f5;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  word-break: break-all;
}

/* 工具列表 */
.tools-section {
  margin-top: 16px;
}

.tools-header {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 12px;
}

.tools-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-item {
  background: #f8f9fa;
  border-radius: 6px;
  overflow: hidden;
}

.tool-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.tool-header:hover {
  background: #f0f1f2;
}

.tool-main {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-weight: 500;
  color: #333;
  font-size: 13px;
  margin-bottom: 4px;
}

.tool-description {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
}

.tool-expand-icon {
  font-size: 10px;
  color: #999;
  margin-left: 8px;
  flex-shrink: 0;
}

/* 工具参数详情 */
.tool-params {
  padding: 12px;
  border-top: 1px solid #e5e5e5;
  background: #fff;
}

.params-title {
  font-size: 12px;
  font-weight: 500;
  color: #666;
  margin-bottom: 10px;
}

.params-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.param-item {
  padding: 8px 10px;
  background: #f5f7f9;
  border-radius: 4px;
  border-left: 3px solid #ddd;
}

.param-item:has(.param-required.required) {
  border-left-color: #ff6b6b;
}

.param-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.param-name {
  font-family: monospace;
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  background: #e8e8e8;
  padding: 2px 6px;
  border-radius: 3px;
}

.param-type {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  background: #e3f2fd;
  color: #1976d2;
  font-family: monospace;
}

.param-required {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  background: #f5f5f5;
  color: #999;
}

.param-required.required {
  background: #ffebee;
  color: #d32f2f;
  font-weight: 500;
}

.param-description {
  font-size: 12px;
  color: #555;
  line-height: 1.4;
  margin-top: 4px;
}

.param-default {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}

.param-default code {
  background: #e8e8e8;
  padding: 1px 4px;
  border-radius: 2px;
  font-family: monospace;
}

.param-enum {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}

.param-enum code {
  background: #e8f5e9;
  color: #2e7d32;
  padding: 1px 4px;
  border-radius: 2px;
  font-family: monospace;
  margin-right: 2px;
}

.no-params {
  font-size: 12px;
  color: #999;
  text-align: center;
  padding: 8px;
}

.no-tools {
  padding: 20px;
  text-align: center;
  color: #999;
  font-size: 13px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;
  color: #999;
}

.empty-state p {
  margin: 16px 0;
}

/* 按钮样式 */
.btn-small {
  padding: 6px 12px;
  font-size: 13px;
}

.btn-icon {
  padding: 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #666;
  border-radius: 4px;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: #e5e5e5;
  color: #333;
}

.btn-icon.btn-danger:hover {
  background: #ffebee;
  color: #d32f2f;
}

.btn-outline {
  background: transparent;
  border: 1px solid #ddd;
  color: #333;
}

.btn-outline:hover {
  background: #f5f5f5;
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid #ddd;
  border-top-color: var(--primary, #ff2442);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 弹窗样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e5e5;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e5e5e5;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.form-group input[type="text"],
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.form-group input[type="text"]:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--primary, #ff2442);
}

.form-group textarea {
  resize: vertical;
  font-family: monospace;
}

.form-select {
  background: white;
  cursor: pointer;
}

.checkbox-label {
  display: flex !important;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-label input {
  width: 16px;
  height: 16px;
}

/* 消息提示 */
.message {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 1001;
  animation: slideUp 0.3s ease;
}

.message.success {
  background: #e6f7e6;
  color: #2e7d32;
}

.message.error {
  background: #ffebee;
  color: #d32f2f;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
