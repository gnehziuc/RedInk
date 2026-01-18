/**
 * Agent API 客户端 - P1-3: 支持新的初始化/启动分离流程
 */
import axios from 'axios'

const API_BASE = '/api/agent/v1'

export interface CreateTaskRequest {
  topic: string
  images?: string[]
  task_id?: string  // 可选，前端预生成的任务 ID（向后兼容）
}

export interface CreateTaskResponse {
  success: boolean
  task_id?: string
  status?: string
  output?: string
  error?: string
  message?: string
}

export interface InitTaskRequest {
  topic: string
  images?: string[]
}

export interface InitTaskResponse {
  success: boolean
  task_id: string
  status: string
  message: string
  error?: string
}

export interface StartTaskResponse {
  success: boolean
  task_id: string
  status: string
  message: string
  error?: string
}

export interface TaskStatus {
  success: boolean
  task_id: string
  status: string
  progress?: number
  current_step?: string
  created_at?: string
  started_at?: string
  completed_at?: string
  error?: string
  result?: any
}

export interface ToolInfo {
  name: string
  description: string
}

/**
 * 初始化任务（仅创建，不执行）- P1-3: 解决 taskId 时序问题
 * 使用此接口可以先获取 task_id，再加入 WebSocket 房间，最后启动任务
 */
export async function initAgentTask(data: InitTaskRequest): Promise<InitTaskResponse> {
  const response = await axios.post(`${API_BASE}/init`, data)
  return response.data
}

/**
 * 启动已初始化的任务
 */
export async function startAgentTask(taskId: string): Promise<StartTaskResponse> {
  const response = await axios.post(`${API_BASE}/start/${taskId}`)
  return response.data
}

/**
 * 创建并立即执行创作任务（向后兼容）
 */
export async function createAgentTask(data: CreateTaskRequest): Promise<CreateTaskResponse> {
  const response = await axios.post(`${API_BASE}/create`, data)
  return response.data
}

/**
 * 获取任务状态
 */
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const response = await axios.get(`${API_BASE}/status/${taskId}`)
  return response.data
}

/**
 * 取消任务
 */
export async function cancelAgentTask(taskId: string): Promise<{ success: boolean; message?: string; error?: string }> {
  const response = await axios.post(`${API_BASE}/cancel/${taskId}`)
  return response.data
}

/**
 * 列出任务
 */
export async function listAgentTasks(options?: { status?: string; limit?: number }): Promise<{ success: boolean; tasks: TaskStatus[]; count: number }> {
  const params = new URLSearchParams()
  if (options?.status) params.append('status', options.status)
  if (options?.limit) params.append('limit', options.limit.toString())

  const response = await axios.get(`${API_BASE}/list?${params.toString()}`)
  return response.data
}

/**
 * 获取可用工具列表
 */
export async function listTools(): Promise<{ tools: string[] }> {
  const response = await axios.get(`${API_BASE}/tools`)
  return response.data
}
