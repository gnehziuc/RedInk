/**
 * 账号状态管理
 * 
 * 使用 Pinia 管理账号列表和刷新状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Account, RawAccountData } from '@/api/account'
import { parseRawAccount, platformTypes } from '@/api/account'

export const useAccountStore = defineStore('account', () => {
    // 账号列表
    const accounts = ref<Account[]>([])

    // 刷新状态
    const isRefreshing = ref(false)

    // 是否是首次访问
    const isFirstTimeVisit = ref(true)

    // 设置账号列表（从原始数据转换）
    function setAccounts(rawData: RawAccountData[]) {
        accounts.value = rawData.map(parseRawAccount)
    }

    // 添加账号
    function addAccount(account: Account) {
        accounts.value.push(account)
    }

    // 更新账号
    function updateAccount(id: number, updatedData: Partial<Account>) {
        const index = accounts.value.findIndex(acc => acc.id === id)
        if (index !== -1) {
            accounts.value[index] = { ...accounts.value[index], ...updatedData }
        }
    }

    // 删除账号
    function deleteAccount(id: number) {
        accounts.value = accounts.value.filter(acc => acc.id !== id)
    }

    // 设置刷新状态
    function setRefreshing(status: boolean) {
        isRefreshing.value = status
    }

    // 标记已访问
    function markVisited() {
        isFirstTimeVisit.value = false
    }

    // 按平台筛选账号
    const kuaishouAccounts = computed(() =>
        accounts.value.filter(acc => acc.platform === '快手')
    )

    const douyinAccounts = computed(() =>
        accounts.value.filter(acc => acc.platform === '抖音')
    )

    const channelsAccounts = computed(() =>
        accounts.value.filter(acc => acc.platform === '视频号')
    )

    const xiaohongshuAccounts = computed(() =>
        accounts.value.filter(acc => acc.platform === '小红书')
    )

    return {
        accounts,
        isRefreshing,
        isFirstTimeVisit,
        setAccounts,
        addAccount,
        updateAccount,
        deleteAccount,
        setRefreshing,
        markVisited,
        kuaishouAccounts,
        douyinAccounts,
        channelsAccounts,
        xiaohongshuAccounts,
        platformTypes
    }
})
