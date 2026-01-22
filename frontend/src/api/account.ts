/**
 * 账号管理 API
 * 
 * 提供账号的 CRUD 操作和 Cookie 管理
 */
import axios from 'axios'

const API_BASE_URL = '/api'

// 账号接口
export interface Account {
  id: number
  type: number
  filePath: string
  name: string
  status: string
  platform: string
  avatar?: string
}

// 原始账号数据格式 (数组)
export type RawAccountData = [number, number, string, string, number]

// 平台类型映射
export const platformTypes: Record<number, string> = {
  1: '小红书',
  2: '视频号',
  3: '抖音',
  4: '快手'
}

// 将原始数据转换为 Account 对象
export function parseRawAccount(raw: RawAccountData): Account {
  return {
    id: raw[0],
    type: raw[1],
    filePath: raw[2],
    name: raw[3],
    status: raw[4] === 1 ? '正常' : '异常',
    platform: platformTypes[raw[1]] || '未知',
    avatar: '/vite.svg'
  }
}

// 获取账号列表（快速，不验证）
export async function getAccounts(): Promise<{
  code: number
  msg: string | null
  data: RawAccountData[]
}> {
  const response = await axios.get(`${API_BASE_URL}/accounts`)
  return response.data
}

// 获取账号列表（带验证）
export async function getValidAccounts(): Promise<{
  code: number
  msg: string | null
  data: RawAccountData[]
}> {
  const response = await axios.get(`${API_BASE_URL}/accounts/valid`)
  return response.data
}

// 删除账号
export async function deleteAccount(id: number): Promise<{
  code: number
  msg: string
  data: null
}> {
  const response = await axios.delete(`${API_BASE_URL}/accounts/${id}`)
  return response.data
}

// 更新账号
export async function updateAccount(data: {
  id: number
  type: number
  userName: string
}): Promise<{
  code: number
  msg: string
  data: null
}> {
  const response = await axios.put(`${API_BASE_URL}/accounts/${data.id}`, data)
  return response.data
}

// 上传 Cookie 文件
export async function uploadCookie(
  id: number,
  platform: string,
  file: File
): Promise<{
  code: number
  msg: string
  data: null
}> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('id', id.toString())
  formData.append('platform', platform)
  
  const response = await axios.post(`${API_BASE_URL}/accounts/cookie/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

// 获取下载 Cookie 的 URL
export function getCookieDownloadUrl(filePath: string): string {
  return `${API_BASE_URL}/accounts/cookie/download?filePath=${encodeURIComponent(filePath)}`
}

// 获取登录 SSE URL
export function getLoginSSEUrl(type: string, id: string): string {
  return `${API_BASE_URL}/accounts/login?type=${type}&id=${encodeURIComponent(id)}`
}
