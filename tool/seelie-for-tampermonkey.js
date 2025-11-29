// ==UserScript==
// @name         Seelie背包物品同步
// @namespace    http://tampermonkey.net/
// @version      1.4
// @description  从指定API获取数据，并将其JSON文本存储到多个 localStorage 键中，支持多UID配置、一次性导入所有账号、自动同步和条件重载。
// @author       Patrick-Ze & Gemini
// @match        https://seelie.me/*
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ====================================================================
    // 1. 配置
    // ====================================================================

    // API 基础 URL，UID 将被附加在末尾
    const API_BASE_URL = 'http://127.0.0.1:20928/inventory/seelie/';

    // UID 到 localStorage 键名的映射表。每次点击按钮将导入所有配置的 UID。
    const UID_CONFIG = {
        "100000001": ["main-inventory"],
        "100000002": ["account-2-inventory"]
    };

    // 按钮 ID
    const BUTTON_ID = 'seelie-api-importer-btn';

    // 当前浏览器会话是否已同步的标记键
    const SESSION_SYNC_KEY = 'seelie_imported_session';

    // 重载延迟时间 (毫秒)
    const RELOAD_DELAY_MS = 1000;

    // ====================================================================
    // 2. CSS 样式 (确保按钮在左上角悬浮)
    // ====================================================================
    GM_addStyle(`
        #${BUTTON_ID} {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 9999;
            background-color: #3b82f6; /* 蓝色背景 */
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: background-color 0.3s, transform 0.1s;
            font-weight: bold;
            font-size: 14px;
            /* 确保文本能够显示当前状态 */
            min-width: 150px;
            text-align: center;
        }
        #${BUTTON_ID}:hover {
            background-color: #2563eb;
            transform: translateY(-1px);
        }
        #${BUTTON_ID}.loading {
            background-color: #f59e0b; /* 加载中颜色 */
            pointer-events: none;
        }
        #${BUTTON_ID}.success {
            background-color: #10b981; /* 成功颜色 */
        }
        #${BUTTON_ID}.error {
            background-color: #ef4444; /* 错误颜色 */
        }
    `);

    // ====================================================================
    // 3. 核心功能：获取数据并存储
    // ====================================================================

    /**
     * 更新按钮状态和文本
     * @param {string} status - 'normal', 'loading', 'success', 'error'
     * @param {string} text - 按钮显示的文本
     */
    function updateButton(status, text) {
        const btn = document.getElementById(BUTTON_ID);
        if (!btn) return;

        btn.className = ''; // 清除所有状态类
        btn.textContent = text;

        if (status !== 'normal') {
            btn.classList.add(status);
        }
    }

    /**
     * 处理单个 UID 的 API 请求和存储操作
     * @param {string} uid - 待导入的 UID
     * @param {string[]} targetKeys - 写入的 localStorage 键数组
     * @returns {Promise<{uid: string, status: 'success' | 'skipped'}>}
     */
    function processSingleUID(uid, targetKeys) {
        return new Promise((resolve, reject) => {
            if (!targetKeys || targetKeys.length === 0) {
                 // 如果键数组为空，则直接跳过
                 resolve({ uid, status: 'skipped' });
                 return;
            }

            const currentApiUrl = API_BASE_URL + uid;

            // 使用 GM_xmlhttpRequest 进行跨域请求
            GM_xmlhttpRequest({
                method: "GET",
                url: currentApiUrl,
                headers: {
                    "accept": "application/json"
                },
                responseType: "text",

                onload: function(response) {
                    if (response.status === 200) {
                        const rawJsonText = response.responseText;

                        try {
                            const parsedData = JSON.parse(rawJsonText);

                            // 检查并提取 inventory 数组
                            if (parsedData && Array.isArray(parsedData.inventory)) {
                                const inventoryJsonText = JSON.stringify(parsedData.inventory);

                                // 存储到所有目标 localStorage 键
                                targetKeys.forEach(key => {
                                    localStorage.setItem(key, inventoryJsonText);
                                });

                                console.log(`[Seelie Importer] 成功导入 UID ${uid} 的 inventory 到键: ${targetKeys.join(', ')}`);
                                resolve({ uid, status: 'success' });

                            } else {
                                console.error(`[Seelie Importer] UID ${uid} 缺少有效的 "inventory" 数组字段。`);
                                reject({ uid, error: '缺少库存数据' });
                            }

                        } catch (e) {
                            console.error(`[Seelie Importer] UID ${uid} API返回数据不是有效的JSON格式:`, e);
                            reject({ uid, error: 'JSON格式错误' });
                        }
                    } else {
                        console.error(`[Seelie Importer] UID ${uid} API请求失败，状态码: ${response.status}.`);
                        reject({ uid, error: `HTTP ${response.status}` });
                    }
                },

                onerror: function(e) {
                    console.error(`[Seelie Importer] UID ${uid} API请求出错（网络/CORS错误）。`, e);
                    reject({ uid, error: '网络错误' });
                }
            });
        });
    }


    /**
     * 协调所有 UID 的 API 请求，并更新按钮状态
     */
    async function startAllImports() {
        const uids = Object.keys(UID_CONFIG);
        const totalUids = uids.length;

        if (totalUids === 0) {
            updateButton('error', '错误: UID_CONFIG为空');
            sessionStorage.setItem(SESSION_SYNC_KEY, 'true');
            setTimeout(() => updateButton('normal', '同步所有账号的背包物品'), 3000);
            return;
        }

        updateButton('loading', `正在导入 ${totalUids} 个账号...`);

        // 准备所有的 Promise
        const promises = uids.map(uid => {
            const targetKeys = UID_CONFIG[uid];
            return processSingleUID(uid, targetKeys);
        });

        // 等待所有请求完成
        const results = await Promise.allSettled(promises);

        const successfulImports = results.filter(r => r.status === 'fulfilled' && r.value.status === 'success').length;
        const failedImports = results.filter(r => r.status === 'rejected').length;

        let finalStatus = 'normal';
        let finalMessage = '更新所有账号的背包物品';

        // 确定最终状态和消息
        if (successfulImports === totalUids) {
            finalStatus = 'success';
            finalMessage = `全部导入成功 (${totalUids} 个)!`;
        } else if (failedImports > 0 || successfulImports < totalUids) {
            finalStatus = 'error';
            finalMessage = `导入完成: ${successfulImports} 成功, ${failedImports} 失败`;
        }

        // 按钮文本将包含重载信息
        let reloadHint = successfulImports > 0 ? ` (${RELOAD_DELAY_MS / 1000}秒后重载)` : " (不重载)";
        updateButton(finalStatus, finalMessage + reloadHint);

        // 设置会话标记，无论是否成功，确保不会自动重复同步
        sessionStorage.setItem(SESSION_SYNC_KEY, 'true');

        // 1. 只在至少有一个账号同步成功时执行reload
        if (successfulImports > 0) {
            // 2. 1秒就reload，节省时间
            setTimeout(() => {
                console.log('[Seelie Importer] 发现成功导入，正在重载页面...');
                window.location.reload();
            }, RELOAD_DELAY_MS);
        } else {
            // 如果没有成功导入，保持按钮状态不变，3秒后恢复正常
            setTimeout(() => updateButton('normal', '更新所有账号的背包物品'), 3000);
        }
    }

    // ====================================================================
    // 4. 初始化和按钮创建
    // ====================================================================

    function createImporterButton() {
        const button = document.createElement('button');
        button.id = BUTTON_ID;
        button.textContent = `更新所有账号的背包物品`; // 按钮文本更改为导入所有

        button.addEventListener('click', startAllImports); // 绑定到新的协调函数

        document.body.appendChild(button);

        // 1. 自动同步逻辑：检查 sessionStorage 中是否有同步标记
        if (sessionStorage.getItem(SESSION_SYNC_KEY) !== 'true') {
            // 如果没有标记，执行自动同步。延迟 500ms 确保 DOM 稳定。
            console.log('[Seelie Importer] 检测到新会话，开始自动导入...');
            // 更新按钮状态以显示正在自动同步
            updateButton('loading', '自动导入中...');
            setTimeout(startAllImports, 500);
        } else {
            console.log('[Seelie Importer] 本会话已同步，跳过自动导入。');
        }
    }

    // 在页面加载完成后创建按钮
    window.addEventListener('load', createImporterButton);

})();
