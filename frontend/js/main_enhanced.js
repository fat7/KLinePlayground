// 全局变量
let currentUser = null;
let chart = null;
let volumeChart = null;
let indicatorChart = null;
let candlestickSeries = null;
let volumeSeries = null;
let maSeries = {}; // 存储移动平均线系列
let indicatorSeries = null;
let tradeMarkerSeries = null;
let isPlaying = false;
let playbackInterval = null;
let currentTraining = null;
let currentIndicatorType = 'MACD';
let currentIndicatorSeries = [];
let bollSeries = {}; // 用于存储BOLL指标线
let autoSyncInterval = null;
let lastKnownBarId = null;
let lastKnownTradeCount = null;
let maPeriods = [5, 10, 20]; // 默认MA周期
const maColors = ['#1d2140', '#2816cf', '#ff8103', '#e02424', '#8b5cf6', '#059669']; // 6个预设颜色

// API 基础URL - 改为相对路径适配动态端口
const API_BASE = '/api';

// 初始化应用
document.addEventListener('DOMContentLoaded', function () {
    initializeApp();
    setupEventListeners();
    setupKeyboardShortcuts();
});

// 初始化应用
async function initializeApp() {
    try {
        // 检查是否有保存的用户
        const savedUser = localStorage.getItem('currentUser');
        if (savedUser) {
            currentUser = savedUser;
            showMainApp();
            await loadUserStatistics();
        } else {
            showUserSelection();
        }

        // 加载用户列表
        await loadUsers();

        // 如果有保存的用户，初始化 AI API 状态
        if (currentUser) {
            fetch(`${API_BASE}/users/${currentUser}/settings`)
                .then(res => res.json())
                .then(settings => {
                    updateAIApiStatus(!!settings.enable_ai_api, currentUser);
                }).catch(e => console.error(e));
        }
    } catch (error) {
        console.error('初始化失败:', error);
        showUserSelection();
    }
}

async function updateAIApiStatus(enabled, username) {
    try {
        await fetch(`${API_BASE}/system/api_info`, {
            method: enabled ? 'POST' : 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user: username })
        });
    } catch (e) {
        console.error('Failed to update AI API status:', e);
    }
}

function renderChartLegend() {
    const container = document.getElementById('chart-legend');
    if (!container) return;
    const items = [];
    maPeriods.forEach(p => {
        if (maSeries[p]) {
            items.push({ label: `MA${p}`, color: maSeries[p].options().color });
        }
    });
    if (bollSeries && bollSeries.upper && bollSeries.middle && bollSeries.lower) {
        items.push({ label: 'UP', color: bollSeries.upper.options().color });
        items.push({ label: 'MID', color: bollSeries.middle.options().color });
        items.push({ label: 'LOW', color: bollSeries.lower.options().color });
    }
    container.innerHTML = '';
    items.forEach(it => {
        const el = document.createElement('span');
        el.className = 'legend-chip';
        el.style.backgroundColor = it.color || '#999';
        el.textContent = it.label;
        container.appendChild(el);
    });
}

function renderIndicatorLegend() {
    const container = document.getElementById('indicator-legend');
    if (!container) return;
    container.innerHTML = '';
    const items = [];
    switch (currentIndicatorType) {
        case 'MACD':
            if (currentIndicatorSeries[0]) items.push({ label: 'DIF', color: currentIndicatorSeries[0].options().color });
            if (currentIndicatorSeries[1]) items.push({ label: 'DEA', color: currentIndicatorSeries[1].options().color });
            items.push({ label: 'MACD', color: '#999' });
            break;
        case 'KDJ':
            if (currentIndicatorSeries[0]) items.push({ label: 'K', color: currentIndicatorSeries[0].options().color });
            if (currentIndicatorSeries[1]) items.push({ label: 'D', color: currentIndicatorSeries[1].options().color });
            if (currentIndicatorSeries[2]) items.push({ label: 'J', color: currentIndicatorSeries[2].options().color });
            break;
        case 'RSI':
            currentIndicatorSeries.forEach(series => {
                items.push({ label: series.rsiTitle || series.options().title || 'RSI', color: series.options().color });
            });
            break;
        case 'BOLL':
            items.push({ label: 'UP', color: '#ff6b6b' });
            items.push({ label: 'MID', color: '#4ecdc4' });
            items.push({ label: 'LOW', color: '#45b7d1' });
            break;
    }
    items.forEach(it => {
        const el = document.createElement('span');
        el.className = 'legend-chip';
        el.style.backgroundColor = it.color || '#999';
        el.textContent = it.label;
        container.appendChild(el);
    });
}
// 设置事件监听器
function setupEventListeners() {
    // 用户选择相关
    document.getElementById('create-user-btn').addEventListener('click', createUser);
    document.getElementById('switch-user-btn').addEventListener('click', showUserSelection);

    // 训练设置相关
    document.getElementById('new-training-btn').addEventListener('click', showTrainingSetup);
    document.getElementById('cancel-setup-btn').addEventListener('click', hideTrainingSetup);
    document.getElementById('start-training-btn').addEventListener('click', startTraining);

    // 设置按钮
    document.getElementById('settings-btn')?.addEventListener('click', showSettings);
    document.getElementById('save-settings-btn')?.addEventListener('click', saveSettings);
    document.getElementById('cancel-settings-btn')?.addEventListener('click', hideSettings);

    // 标签页切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            switchTab(this.dataset.tab);
        });
    });

    // 回放控制
    document.getElementById('play-pause-btn').addEventListener('click', togglePlayback);
    document.getElementById('next-bar-btn').addEventListener('click', nextBar);
    document.getElementById('playback-speed').addEventListener('change', updatePlaybackSpeed);

    // 复权设置
    document.querySelectorAll('input[name="adjustment"]').forEach(radio => {
        radio.addEventListener('change', updateAdjustment);
    });

    // 交易操作
    document.getElementById('buy-btn').addEventListener('click', executeBuy);
    document.getElementById('sell-btn').addEventListener('click', executeSell);

    // 交易数量输入限制
    document.getElementById('trade-quantity').addEventListener('input', limitTradeQuantity);

    // 训练控制
    document.getElementById('end-training-btn').addEventListener('click', endTraining);
    document.getElementById('reset-training-btn').addEventListener('click', resetTraining);

    // 技术指标选择
    document.getElementById('indicator-select')?.addEventListener('change', changeIndicator);

    // 复盘报告
    document.getElementById('view-full-chart-btn').addEventListener('click', viewFullChart);
    document.getElementById('ai-analyze-btn').addEventListener('click', requestAIAnalysis);
    // document.getElementById('new-training-from-report-btn').addEventListener('click', showTrainingSetup);
    document.getElementById('new-training-from-report-btn').addEventListener('click', () => {
        // 1. 调用全局重置函数，清理一切旧状态
        resetToMainAppState();

        // 2. 紧接着，显示新的训练设置界面
        showTrainingSetup();
    });


    // 监听窗口大小变化
    window.addEventListener('resize', resizeCharts);
}

// 设置键盘快捷键
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function (event) {
        // 只在训练界面激活快捷键
        if (document.getElementById('training-interface').classList.contains('hidden') || isViewOnlyMode) {
            return;
        }

        // 如果是由于按住按键导致的重复触发，则忽略大多数操作
        // 但允许数字键的重复输入（如果焦点在输入框内）
        if (event.repeat) {
            // 检查当前焦点是否在输入框，如果不在，则阻止所有重复事件
            const quantityInput = document.getElementById('trade-quantity');
            if (document.activeElement !== quantityInput) {
                return;
            }
            // 如果焦点在输入框，且按下的不是数字，也阻止
            if (!/^[0-9]$/.test(event.key)) {
                return;
            }
            // 此时，允许在输入框中按住数字键进行输入
        }

        const quantityInput = document.getElementById('trade-quantity');
        const isInputFocused = document.activeElement === quantityInput;

        switch (event.key.toLowerCase()) {
            case 'b':
            case '+':
            case '=':
                event.preventDefault(); // 阻止默认行为（如输入'b'或'+'）
                executeBuy();
                break;

            case 's':
            case '-':
                event.preventDefault(); // 阻止默认行为
                executeSell();
                break;

            case ' ':
            case 'enter':
                event.preventDefault();
                nextBar();
                break;

            case '0': case '1': case '2': case '3': case '4':
            case '5': case '6': case '7': case '8': case '9':
                if (!isInputFocused) {
                    event.preventDefault();
                    quantityInput.focus();
                    quantityInput.value = event.key;
                }
                // 如果焦点已在输入框，则不作处理，允许默认的输入行为
                // 这样用户就可以正常输入多位数，并且按住数字键也能连续输入
                break;
        }

    });
}

// 处理窗口大小变化
function resizeCharts() {
    if (chart && !document.getElementById('training-interface').classList.contains('hidden')) {
        const chartContainer = document.getElementById('chart');
        const volumeContainer = document.getElementById('volume-chart');
        const indicatorContainer = document.getElementById('indicator-chart');

        chart.resize(chartContainer.clientWidth, chartContainer.clientHeight);
        volumeChart.resize(volumeContainer.clientWidth, volumeContainer.clientHeight);
        indicatorChart.resize(indicatorContainer.clientWidth, indicatorContainer.clientHeight);
    }
}

// 用户管理
async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE}/users`);
        const users = await response.json();

        const container = document.getElementById('existing-users');
        container.innerHTML = '';

        users.forEach(user => {
            const userItem = document.createElement('div');
            userItem.className = 'user-item';
            userItem.textContent = user;

            let pressTimer;

            // 鼠标长按事件
            userItem.addEventListener('mousedown', () => {
                pressTimer = window.setTimeout(() => {
                    // 长按触发删除确认
                    if (confirm(`确定要永久删除用户 "${user}" 吗？此操作不可恢复！`)) {
                        deleteUser(user);
                    }
                }, 1000); // 1秒后触发
            });

            userItem.addEventListener('mouseup', () => {
                clearTimeout(pressTimer);
            });

            userItem.addEventListener('mouseleave', () => {
                clearTimeout(pressTimer);
            });

            // 触摸长按事件 (移动端支持)
            userItem.addEventListener('touchstart', () => {
                pressTimer = window.setTimeout(() => {
                    if (confirm(`确定要永久删除用户 "${user}" 吗？此操作不可恢复！`)) {
                        deleteUser(user);
                    }
                }, 1000);
            });

            userItem.addEventListener('touchend', () => {
                clearTimeout(pressTimer);
            });

            userItem.addEventListener('touchmove', () => {
                clearTimeout(pressTimer);
            });

            // 单击事件
            userItem.addEventListener('click', (e) => {
                // 防止长按后还触发单击
                if (e.detail) { // e.detail > 0 for real clicks
                    selectUser(user);
                }
            });

            container.appendChild(userItem);
        });
    } catch (error) {
        console.error('加载用户列表失败:', error);
    }
}

async function createUser() {
    const username = document.getElementById('new-username').value.trim();
    if (!username) {
        alert('请输入用户名');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username })
        });

        if (response.ok) {
            await loadUsers();
            document.getElementById('new-username').value = '';
            selectUser(username);
        } else {
            const error = await response.json();
            alert(error.message || '创建用户失败');
        }
    } catch (error) {
        console.error('创建用户失败:', error);
        alert('创建用户失败');
    }
}

async function deleteUser(username) {
    try {
        const response = await fetch(`${API_BASE}/users/${username}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            alert(`用户 "${username}" 已成功删除。`);
            await loadUsers(); // 重新加载用户列表
        } else {
            const error = await response.json();
            alert(error.message || '删除用户失败');
        }
    } catch (error) {
        console.error('删除用户失败:', error);
        alert('删除用户时发生网络错误。');
    }
}

function selectUser(username) {
    currentUser = username;
    localStorage.setItem('currentUser', username);
    document.getElementById('current-username').textContent = username;
    showMainApp();
    loadUserStatistics();

    // 初始化 AI API 状态
    fetch(`${API_BASE}/users/${username}/settings`)
        .then(res => res.json())
        .then(settings => {
            updateAIApiStatus(!!settings.enable_ai_api, username);
        }).catch(e => console.error(e));
}

async function loadUserStatistics() {
    if (!currentUser) return;

    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/statistics`);
        const stats = await response.json();

        // 显示用户统计信息
        const statsElement = document.getElementById('user-stats');
        if (statsElement) {
            statsElement.innerHTML = `
                <div class="stat-item">
                    <span>历史总收益:</span>
                    <span class="${stats.avg_return >= 0 ? 'positive' : 'negative'}">${stats.avg_return.toFixed(2)}%</span>
                </div>
                <div class="stat-item">
                    <span>局胜率:</span>
                    <span class="${stats.avg_session_win_rate >= 50 ? 'positive' : 'negative'}">${stats.avg_session_win_rate.toFixed(2)}%</span>
                </div>
                <div class="stat-item">
                    <span>总训练次数:</span>
                    <span>${stats.total_sessions}</span>
                </div>
            `;
        }
    } catch (error) {
        console.error('加载用户统计失败:', error);
    }
}

/**
 * 控制顶部工具栏在训练期间的元素可见性
 * @param {boolean} isTraining - 是否正在进行训练
 */
function toggleToolbarForTraining(isTraining) {
    const elementsToToggle = [
        document.getElementById('switch-user-btn'),
        document.getElementById('settings-btn'),
        document.getElementById('new-training-btn'),
        document.getElementById('main-title') // 新增的标题元素
    ];

    elementsToToggle.forEach(el => {
        if (el) { // 确保元素存在
            el.classList.toggle('hidden', isTraining);
        }
    });
}

/**
 * 重置整个训练环境，回到主应用界面
 * 用于从复盘报告或训练界面返回时，清理所有状态
 */
function resetToMainAppState() {
    // 1. 暂停任何正在进行的回放
    if (isPlaying) {
        pausePlayback();
    }
    stopAutoSync();

    // 2. 清理图表对象和数据
    if (chart) {
        chart.remove();
        chart = null;
    }
    if (volumeChart) {
        volumeChart.remove();
        volumeChart = null;
    }
    if (indicatorChart) {
        indicatorChart.remove();
        indicatorChart = null;
    }
    // 清空图表容器，确保 Lightweight Charts 的 DOM 被彻底移除
    document.getElementById('chart').innerHTML = '';
    document.getElementById('volume-chart').innerHTML = '';
    document.getElementById('indicator-chart').innerHTML = '';

    // 3. 重置所有图表系列变量
    candlestickSeries = null;
    volumeSeries = null;
    maSeries = {};
    indicatorSeries = null;
    tradeMarkerSeries = null;
    currentIndicatorSeries = [];
    bollSeries = {};

    // 4. 清理界面上的动态数据
    // 清理交易记录
    document.getElementById('trade-history').innerHTML = '<div class="no-trades">暂无交易记录</div>';
    // 清理持仓信息
    document.getElementById('current-positions').innerHTML = '<div class="no-positions">暂无持仓</div>';
    // 清理账户信息
    document.getElementById('total-assets').textContent = '¥-';
    document.getElementById('available-cash').textContent = '¥-';
    document.getElementById('position-value').textContent = '¥-';
    document.getElementById('floating-pnl').textContent = '¥-';
    document.getElementById('floating-pnl').style.color = '#000000';
    document.getElementById('max-buy-quantity').textContent = '0';
    document.getElementById('max-sell-quantity').textContent = '0';
    document.getElementById('trade-quantity').value = '1'; // 重置交易数量
    // 清理K线信息
    document.getElementById('stock-name').textContent = '未知股票';
    document.getElementById('current-date').textContent = 'YYYY/MM/DD';
    document.getElementById('current-price').textContent = '¥-.--';
    document.getElementById('current-bar-id').textContent = 'Bar ID: N/A';
    document.getElementById('training-progress').textContent = '进度: -';


    // 5. 重置全局状态变量
    currentTraining = null;
    isPlaying = false;

    // 6. 隐藏所有主要界面，然后显示主应用界面
    document.getElementById('training-interface').classList.add('hidden');
    document.getElementById('report-interface').classList.add('hidden');
    document.getElementById('user-selection').classList.add('hidden');
    document.getElementById('main-app').classList.remove('hidden');

    // Reset view-only mode visually
    document.querySelectorAll('.trade-controls button').forEach(btn => {
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
    });
    
    const endBtn = document.getElementById('end-training-btn');
    if (endBtn) {
        endBtn.disabled = false;
        endBtn.style.opacity = '1';
    }

    const nextBarBtn = document.getElementById('next-bar-btn');
    if (nextBarBtn) {
        nextBarBtn.disabled = false;
        nextBarBtn.style.opacity = '1';
    }
    
    const playPauseBtn = document.getElementById('play-pause-btn');
    if (playPauseBtn) {
        playPauseBtn.disabled = false;
        playPauseBtn.style.opacity = '1';
    }
    
    isViewOnlyMode = false;
    
    const backBtn = document.getElementById('back-to-report-btn');
    if (backBtn) {
        backBtn.classList.add('hidden');
    }

    // 清理后端的训练会话
    if (currentTraining && currentTraining.id) {
        fetch(`${API_BASE}/training/${currentTraining.id}/cleanup`, { method: 'POST' })
            .catch(e => console.error('Cleanup failed:', e));
    }
    
    // Clear current report data and training data
    currentReportData = null;
    currentTraining = null;

    // 7. 确保主界面的工具栏是可见的
    toggleToolbarForTraining(false);
}

// 界面切换
function showUserSelection() {
    document.getElementById('user-selection').classList.remove('hidden');
    document.getElementById('main-app').classList.add('hidden');
    document.getElementById('training-interface').classList.add('hidden');
    document.getElementById('report-interface').classList.add('hidden');
    currentUser = null;
    localStorage.removeItem('currentUser');
}

function showMainApp() {
    document.getElementById('user-selection').classList.add('hidden');
    document.getElementById('main-app').classList.remove('hidden');
    document.getElementById('training-interface').classList.add('hidden');
    document.getElementById('report-interface').classList.add('hidden');

    // 确保按钮和标题是可见的
    toggleToolbarForTraining(false);
}

async function showTrainingSetup() {
    if (currentUser) {
        try {
            const response = await fetch(`${API_BASE}/users/${currentUser}/settings`);
            const settings = await response.json();
            // 应用默认初始资金，如果不存在则使用100000
            document.getElementById('initial-capital').value = settings.default_initial_capital || 100000;
        } catch (error) {
            console.error('加载用户默认资金失败:', error);
            // 加载失败时使用硬编码的默认值
            document.getElementById('initial-capital').value = 100000;
        }
    }
    document.getElementById('training-setup').classList.remove('hidden');
    // 设置默认日期为一年前
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    document.getElementById('start-date').value = oneYearAgo.toISOString().split('T')[0];
}

function hideTrainingSetup() {
    document.getElementById('training-setup').classList.add('hidden');
}

function showSettings() {
    document.getElementById('settings-modal').classList.remove('hidden');
    loadUserSettings();
}

function renderMaPeriodsEditor() {
    const container = document.getElementById('ma-periods-editor');
    if (!container) return;
    container.innerHTML = '';

    maPeriods.forEach((p, index) => {
        const tag = document.createElement('div');
        tag.className = 'ma-period-tag';
        tag.style.cssText = 'background:#f3f4f6; border:1px solid #d1d5db; border-radius:4px; padding:2px 8px; display:flex; align-items:center; font-size:12px;';
        tag.innerHTML = `
            <span style="margin-right:8px; font-weight:bold;">${p}</span>
            <span class="delete-ma" data-index="${index}" style="cursor:pointer; color:#ef4444; font-weight:bold;">×</span>
        `;
        container.appendChild(tag);
    });

    if (maPeriods.length < 6) {
        const addBtn = document.createElement('button');
        addBtn.className = 'btn-add-ma';
        addBtn.style.cssText = 'background:#e5e7eb; border:none; border-radius:4px; width:24px; height:24px; cursor:pointer; display:flex; align-items:center; justify-content:center; font-weight:bold;';
        addBtn.textContent = '+';
        addBtn.onclick = () => {
            const val = prompt('输入新的均线周期 (如: 60):');
            if (val && !isNaN(val)) {
                const p = parseInt(val);
                if (p > 0 && !maPeriods.includes(p)) {
                    maPeriods.push(p);
                    maPeriods.sort((a, b) => a - b);
                    renderMaPeriodsEditor();
                }
            }
        };
        container.appendChild(addBtn);
    }

    // 删除事件
    container.querySelectorAll('.delete-ma').forEach(btn => {
        btn.onclick = (e) => {
            const idx = parseInt(e.target.dataset.index);
            maPeriods.splice(idx, 1);
            renderMaPeriodsEditor();
        };
    });
}

function hideSettings() {
    document.getElementById('settings-modal').classList.add('hidden');
}

async function loadUserSettings() {
    if (!currentUser) return;

    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/settings`);
        const settings = await response.json();

        document.getElementById('default-initial-capital').value = settings.default_initial_capital || 100000;
        document.getElementById('commission-rate').value = (settings.commission_rate * 10000).toFixed(1);
        document.getElementById('min-commission').value = settings.min_commission;
        document.getElementById('stamp-tax-rate').value = (settings.stamp_tax_rate * 1000).toFixed(1);

        // 加载复权方式设置
        if (settings.adjustment_mode) {
            document.getElementById('adjustment-mode').value = settings.adjustment_mode;
            // 同时更新左侧面板的复权设置
            const adjustmentRadio = document.querySelector(`input[name="adjustment"][value="${settings.adjustment_mode}"]`);
            if (adjustmentRadio) {
                adjustmentRadio.checked = true;
            }
        }

        // 加载 AI API 设置
        if (settings.enable_ai_api !== undefined) {
            document.getElementById('enable-ai-api').checked = settings.enable_ai_api;
        } else {
            document.getElementById('enable-ai-api').checked = false;
        }

        // 加载MA周期
        if (settings.ma_periods && Array.isArray(settings.ma_periods)) {
            maPeriods = [...settings.ma_periods];
        } else {
            maPeriods = [5, 10, 20];
        }
        renderMaPeriodsEditor();
    } catch (error) {
        console.error('加载用户设置失败:', error);
    }
}

async function saveSettings() {
    if (!currentUser) return;

    try {
        const settings = {
            default_initial_capital: parseInt(document.getElementById('default-initial-capital').value, 10),
            commission_rate: parseFloat(document.getElementById('commission-rate').value) / 10000,
            min_commission: parseFloat(document.getElementById('min-commission').value),
            stamp_tax_rate: parseFloat(document.getElementById('stamp-tax-rate').value) / 1000,
            adjustment_mode: document.getElementById('adjustment-mode').value,
            enable_ai_api: document.getElementById('enable-ai-api').checked,
            ma_periods: maPeriods
        };

        const response = await fetch(`${API_BASE}/users/${currentUser}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            // 同时更新左侧面板的复权设置
            const adjustmentRadio = document.querySelector(`input[name="adjustment"][value="${settings.adjustment_mode}"]`);
            if (adjustmentRadio) {
                adjustmentRadio.checked = true;
            }

            // 更新 AI 接口信息
            updateAIApiStatus(settings.enable_ai_api, currentUser);

            hideSettings();
            alert('设置保存成功');
        } else {
            alert('设置保存失败');
        }
    } catch (error) {
        console.error('保存设置失败:', error);
        alert('保存设置失败');
    }
}

function switchTab(tabName) {
    // 更新标签按钮状态
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // 更新标签内容显示
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-tab`);
    });
}

// 训练管理
async function startTraining() {
    const isRandomMode = document.querySelector('.tab-btn.active').dataset.tab === 'random';
    const initialCapital = parseFloat(document.getElementById('initial-capital').value);
    const dataSource = document.getElementById('data-source').value || 'akshare';

    let trainingConfig = {
        user: currentUser,
        initial_capital: initialCapital,
        mode: isRandomMode ? 'random' : 'specified',
        data_source: dataSource
    };

    if (isRandomMode) {
        trainingConfig.sector = document.getElementById('sector-filter').value;
        trainingConfig.year_range = document.getElementById('year-range').value;
    } else {
        const stockCode = document.getElementById('stock-code').value.trim();
        const startDate = document.getElementById('start-date').value;

        if (!stockCode || !startDate) {
            alert('请填写完整的股票代码和起始日期');
            return;
        }

        trainingConfig.stock_code = stockCode;
        trainingConfig.start_date = startDate;
    }

    try {
        const response = await fetch(`${API_BASE}/training/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(trainingConfig)
        });

        if (response.ok) {
            currentTraining = await response.json();
            hideTrainingSetup();
            showTrainingInterface();
            initializeChart();
            await loadInitialData();

            // 在所有内容加载完毕后，自动触发一次 nextBar
            // 我们加一个小的延时，确保图表渲染完成，视觉效果更平滑
            setTimeout(() => {
                nextBar();
            }, 100); // 100毫秒的延时

            startAutoSync();
        } else {
            const error = await response.json();
            alert(error.message || '开始训练失败');
        }
    } catch (error) {
        console.error('开始训练失败:', error);
        alert('开始训练失败');
    }
}

function showTrainingInterface() {
    document.getElementById('training-interface').classList.remove('hidden');
    updateAccountInfo();
    // 隐藏按钮和标题
    toggleToolbarForTraining(true);
}

// 图表管理
function initializeChart() {
    // 初始化主图表
    const chartContainer = document.getElementById('chart');
    chartContainer.innerHTML = '';

    // 在图表容器内动态创建信息显示框
    const infoDisplay = document.createElement('div');
    infoDisplay.id = 'chart-info-display';
    infoDisplay.className = 'chart-info-display';
    chartContainer.appendChild(infoDisplay);

    const chartLegend = document.createElement('div');
    chartLegend.id = 'chart-legend';
    chartLegend.className = 'chart-legend';
    chartContainer.appendChild(chartLegend);

    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
        layout: {
            backgroundColor: '#ffffff',
            textColor: '#333',
        },
        grid: {
            vertLines: {
                color: '#f0f0f0',
            },
            horzLines: {
                color: '#f0f0f0',
            },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#e9ecef',
        },
        // 使用 localization 选项来格式化十字标线的时间
        localization: {
            // timeFormatter 用于格式化十字标线悬浮窗中的时间
            timeFormatter: (businessDay) => {
                // businessDay 是一个 Date 对象，包含了年、月、日
                // 注意：这里的 businessDay 是一个 UTC 日期对象，所以使用 getUTCFullYear 等方法可以避免时区问题
                const date = new Date(businessDay * 1000);

                const year = date.getUTCFullYear();
                const month = ('0' + (date.getUTCMonth() + 1)).slice(-2); // 月份从0开始
                const day = ('0' + date.getUTCDate()).slice(-2);

                return `${year}年${month}月${day}日`;
            },
            locale: 'zh-CN',
        },
        timeScale: {
            borderColor: '#e9ecef',
            timeVisible: true,
            secondsVisible: false,
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
            }
        },
    });

    // 添加K线系列
    candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: 'rgba(255, 77, 79, 0)',
        downColor: '#008000',
        borderUpColor: '#ff4d4f',
        borderDownColor: '#008000',
        wickUpColor: '#ff4d4f',
        wickDownColor: '#008000',
        borderVisible: true,
    });
    candlestickSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });

    // 添加移动平均线
    maPeriods.forEach((p, index) => {
        maSeries[p] = chart.addSeries(LightweightCharts.LineSeries, {
            color: maColors[index % maColors.length],
            lineWidth: 1,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        maSeries[p].applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
    });

    renderChartLegend();

    // 添加交易标记系列
    tradeMarkerSeries = chart.addSeries(LightweightCharts.LineSeries, {
        color: 'transparent',
        lineWidth: 0,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false
    });
    tradeMarkerSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });

    // 初始化成交量图表
    const volumeContainer = document.getElementById('volume-chart');
    volumeContainer.innerHTML = '';

    volumeChart = LightweightCharts.createChart(volumeContainer, {
        width: volumeContainer.clientWidth,
        height: volumeContainer.clientHeight,
        layout: {
            backgroundColor: '#ffffff',
            textColor: '#333',
        },
        grid: {
            vertLines: {
                color: '#f0f0f0',
            },
            horzLines: {
                color: '#f0f0f0',
            },
        },
        rightPriceScale: {
            borderColor: '#e9ecef',
        },
        timeScale: {
            borderColor: '#e9ecef',
            visible: false,
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
            }
        },
    });

    // 添加成交量系列
    volumeSeries = volumeChart.addSeries(LightweightCharts.HistogramSeries, {
        color: '#26a69a',
        priceFormat: {
            type: 'volume',
        },
        priceLineVisible: false,
        lastValueVisible: false
    });

    // 初始化技术指标图表
    const indicatorContainer = document.getElementById('indicator-chart');
    indicatorContainer.innerHTML = '';

    // 在图表容器内动态创建信息显示框
    const infoDisplay_2 = document.createElement('div');
    infoDisplay_2.id = 'indicator-info-display';
    infoDisplay_2.className = 'chart-info-display';
    indicatorContainer.appendChild(infoDisplay_2);

    const indicatorLegend = document.createElement('div');
    indicatorLegend.id = 'indicator-legend';
    indicatorLegend.className = 'chart-legend';
    indicatorContainer.appendChild(indicatorLegend);

    indicatorChart = LightweightCharts.createChart(indicatorContainer, {
        width: indicatorContainer.clientWidth,
        height: indicatorContainer.clientHeight,
        layout: {
            backgroundColor: '#ffffff',
            textColor: '#333',
        },
        grid: {
            vertLines: {
                color: '#f0f0f0',
            },
            horzLines: {
                color: '#f0f0f0',
            },
        },
        rightPriceScale: {
            borderColor: '#e9ecef',
        },
        timeScale: {
            borderColor: '#e9ecef',
            visible: false,
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
            }
        },
    });

    // 监听主图表（K线图）的时间轴变化
    chart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange) { // 增加一个 null 检查
            volumeChart.timeScale().setVisibleLogicalRange(timeRange);
            indicatorChart.timeScale().setVisibleLogicalRange(timeRange);
        }
    });

    // 监听成交量图表的时间轴变化
    volumeChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange) {
            chart.timeScale().setVisibleLogicalRange(timeRange);
            indicatorChart.timeScale().setVisibleLogicalRange(timeRange);
        }
    });

    // 监听技术指标图表的时间轴变化
    indicatorChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange) {
            chart.timeScale().setVisibleLogicalRange(timeRange);
            volumeChart.timeScale().setVisibleLogicalRange(timeRange);
        }
    });

    function getCrosshairDataPoint(series, param) {
        if (!param.time) {
            return null;
        }
        const dataPoint = param.seriesData.get(series);
        return dataPoint || null;
    }

    function syncCrosshair(chart, series, dataPoint) {
        if (dataPoint) {
            chart.setCrosshairPosition(dataPoint.value, dataPoint.time, series);
            return;
        }
        chart.clearCrosshairPosition();
    }


    chart.subscribeCrosshairMove(param => {
        const infoEl = document.getElementById('chart-info-display');
        if (!param.time || param.point.x < 0 || param.point.y < 0) {
            infoEl.style.display = 'none';
            // 同步其他图表的十字准星
            syncCrosshair(volumeChart, volumeSeries, null);
            if (currentIndicatorSeries.length > 0) {
                syncCrosshair(indicatorChart, currentIndicatorSeries[0], null);
            }
            return;
        }

        infoEl.style.display = 'block';

        // 创建数据Map以便快速查找
        const seriesData = candlestickSeries.data();
        const dataMap = new Map();
        seriesData.forEach((dataPoint, index) => {
            // 确保数据点有时间属性
            if (dataPoint.time) {
                dataMap.set(dataPoint.time, { ...dataPoint, index });
            }
        });

        // 从Map中快速获取当前数据点及其索引
        const currentDataPoint = dataMap.get(param.time);

        if (!currentDataPoint) {
            return;
        }

        let previousDataPoint = null;
        // 检查是否存在前一个数据点
        if (currentDataPoint.index > 0) {
            // 直接通过索引从原始数据数组中获取
            previousDataPoint = seriesData[currentDataPoint.index - 1];
        }

        // 获取K线数据
        const ohlcData = param.seriesData.get(candlestickSeries);
        let ohlcHtml = '数据加载中...';
        if (ohlcData) {
            if (previousDataPoint) {
                ohlcHtml = `
                    <div style="margin-bottom: 4px;">
                        <strong>开:</strong> <span style="color: ${ohlcData.open > previousDataPoint.close ? '#ff4d4f' : ohlcData.open < previousDataPoint.close ? '#008000' : '#000000'};">${ohlcData.open.toFixed(2)}</span>
                        <strong>高:</strong> <span style="color: ${ohlcData.high > previousDataPoint.close ? '#ff4d4f' : ohlcData.high < previousDataPoint.close ? '#008000' : '#000000'};">${ohlcData.high.toFixed(2)}</span>
                        <strong>低:</strong> <span style="color: ${ohlcData.low > previousDataPoint.close ? '#ff4d4f' : ohlcData.low < previousDataPoint.close ? '#008000' : '#000000'};">${ohlcData.low.toFixed(2)}</span>
                        <strong>收: <span style="color: ${ohlcData.close > ohlcData.open ? '#ff4d4f' : ohlcData.close > ohlcData.open ? '#008000' : '#000000'};">${ohlcData.close.toFixed(2)}</span></strong>
                    </div>
                `;
            } else {
                ohlcHtml = `
                    <div style="margin-bottom: 4px;">
                        <strong>开:</strong> <span>${ohlcData.open.toFixed(2)}</span>
                        <strong>高:</strong> <span>${ohlcData.high.toFixed(2)}</span>
                        <strong>低:</strong> <span>${ohlcData.low.toFixed(2)}</span>
                        <strong>收: <span style="color: ${ohlcData.close > ohlcData.open ? '#ff4d4f' : ohlcData.close < ohlcData.open ? '#008000' : '#000000'};">${ohlcData.close.toFixed(2)}</span></strong>
                    </div>
                `;
            }
        }

        // 获取MA数据
        let maHtml = '<div>';
        maPeriods.forEach(p => {
            const mData = param.seriesData.get(maSeries[p]);
            if (mData) {
                maHtml += `<span style="color: ${maSeries[p].options().color};">MA${p}:${mData.value.toFixed(2)} </span>`;
            }
        });
        maHtml += '</div>';

        // 获取并显示BOLL指标数据
        let bollHtml = '';
        // 检查BOLL指标是否处于激活状态 (通过检查bollSeries对象)
        if (currentIndicatorType === 'BOLL' && bollSeries.upper && bollSeries.middle && bollSeries.lower) {
            const upperData = param.seriesData.get(bollSeries.upper);
            const middleData = param.seriesData.get(bollSeries.middle);
            const lowerData = param.seriesData.get(bollSeries.lower);

            if (upperData && middleData && lowerData) {
                bollHtml = `
                    <div id="boll-info-content" style="margin-top: 4px;">
                        <span style="color: ${bollSeries.upper.options().color};">UP:${upperData.value.toFixed(2)} </span>
                        <span style="color: ${bollSeries.middle.options().color};">MID:${middleData.value.toFixed(2)} </span>
                        <span style="color: ${bollSeries.lower.options().color};">LOW:${lowerData.value.toFixed(2)} </span>
                    </div>
                `;
            }
        }

        // 组合所有信息并更新到DOM
        infoEl.innerHTML = ohlcHtml + maHtml + bollHtml;

        // 同步其他图表的十字准星
        const dataPoint = getCrosshairDataPoint(candlestickSeries, param);
        syncCrosshair(volumeChart, volumeSeries, dataPoint);
        if (currentIndicatorSeries.length > 0) {
            syncCrosshair(indicatorChart, currentIndicatorSeries[0], dataPoint);
        }
    });

    volumeChart.subscribeCrosshairMove(param => {
        const dataPoint = getCrosshairDataPoint(volumeSeries, param);
        syncCrosshair(chart, candlestickSeries, dataPoint);
        if (currentIndicatorSeries.length > 0) {
            syncCrosshair(indicatorChart, currentIndicatorSeries[0], dataPoint);
        }
    });

    indicatorChart.subscribeCrosshairMove(param => {
        const infoEl = document.getElementById('indicator-info-display');
        if (!infoEl) return;

        // 如果十字准星移出图表或没有数据，则隐藏信息框
        if (!param.time || param.point.x < 0 || param.point.y < 0 || currentIndicatorSeries.length === 0) {
            infoEl.style.display = 'none';
            return;
        }

        infoEl.style.display = 'block';
        let indicatorHtml = '';

        // 根据当前指标类型，获取并格式化数据
        switch (currentIndicatorType) {
            case 'MACD':
                const difData = param.seriesData.get(currentIndicatorSeries[0]);
                const deaData = param.seriesData.get(currentIndicatorSeries[1]);
                const histData = param.seriesData.get(currentIndicatorSeries[2]);
                if (difData && deaData && histData) {
                    indicatorHtml = `
                        <div><strong>MACD</strong></div>
                        <div style="color: ${currentIndicatorSeries[0].options().color};">DIF: ${difData.value.toFixed(2)}</div>
                        <div style="color: ${currentIndicatorSeries[1].options().color};">DEA: ${deaData.value.toFixed(2)}</div>
                        <div style="color: ${histData.color};">HIST: ${histData.value.toFixed(2)}</div>
                    `;
                }
                break;

            case 'KDJ':
                const kData = param.seriesData.get(currentIndicatorSeries[0]);
                const dData = param.seriesData.get(currentIndicatorSeries[1]);
                const jData = param.seriesData.get(currentIndicatorSeries[2]);
                if (kData && dData && jData) {
                    indicatorHtml = `
                        <div><strong>KDJ</strong></div>
                        <div style="color: ${currentIndicatorSeries[0].options().color};">K: ${kData.value.toFixed(2)}</div>
                        <div style="color: ${currentIndicatorSeries[1].options().color};">D: ${dData.value.toFixed(2)}</div>
                        <div style="color: ${currentIndicatorSeries[2].options().color};">J: ${jData.value.toFixed(2)}</div>
                    `;
                }
                break;

            case 'RSI':
                indicatorHtml = '<div><strong>RSI</strong></div>';
                currentIndicatorSeries.forEach(series => {
                    const rsiData = param.seriesData.get(series);
                    if (rsiData) {
                        const titleText = series.rsiTitle || series.options().title || 'RSI';
                        indicatorHtml += `<div style="color: ${series.options().color};">${titleText}: ${rsiData.value.toFixed(2)}</div>`;
                    }
                });
                break;
        }

        infoEl.innerHTML = indicatorHtml;

        // 同步其他图表的十字准星
        if (currentIndicatorSeries.length > 0) {
            const dataPoint = getCrosshairDataPoint(currentIndicatorSeries[0], param);
            syncCrosshair(chart, candlestickSeries, dataPoint);
            syncCrosshair(volumeChart, volumeSeries, dataPoint);
        }
    });

}

// async function loadInitialData() {
//     try {
//         const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data`);
//         const data = await response.json();
//
//         // 更新股票信息
//         document.getElementById('stock-name').textContent = data.stock_name || '未知股票';
//
//         // 加载初始K线数据
//         if (data.kline_data && data.kline_data.length > 0) {
//             candlestickSeries.setData(data.kline_data);
//             volumeSeries.setData(data.volume_data);
//
//             // 加载移动平均线数据
//             if (data.ma_data) {
//                 maSeries[5].setData(data.ma_data[5] || []);
//                 maSeries[10].setData(data.ma_data[10] || []);
//                 maSeries[20].setData(data.ma_data[20] || []);
//             }
//
//             // 更新当前日期和价格信息
//             const currentBar = data.kline_data[data.kline_data.length - 1];
//             updateCurrentInfo(currentBar, data.progress);
//
//             // 加载交易标记
//             updateTradeMarkers(data.trade_markers || []);
//         }
//
//         // 加载技术指标
//         await loadTechnicalIndicator(currentIndicatorType);
//
//         updateAccountInfo();
//
//     } catch (error) {
//         console.error('加载初始数据失败:', error);
//         alert('加载数据失败');
//     }
// }
/**
 * 加载初始训练数据。
 * 包含一次自动重置和重试的容错逻辑。
 */
async function loadInitialData() {
    // 内部函数，用于执行实际的数据加载尝试
    const attemptToLoad = async () => {
        const maQuery = maPeriods.join(',');
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data?ma_periods=${maQuery}`);
        if (!response.ok) {
            // 如果响应不成功，直接抛出错误，由外部的catch块处理
            throw new Error(`Server responded with status: ${response.status}`);
        }
        const data = await response.json();

        // 更新股票信息
        document.getElementById('stock-name').textContent = data.stock_name || '未知股票';

        // 加载初始K线数据
        if (data.kline_data && data.kline_data.length > 0) {
            candlestickSeries.setData(data.kline_data);
            volumeSeries.setData(data.volume_data);

            // 加载移动平均线数据
            if (data.ma_data) {
                maPeriods.forEach(p => {
                    if (maSeries[p] && data.ma_data[p]) {
                        maSeries[p].setData(data.ma_data[p]);
                    }
                });
            }

            // 更新当前日期和价格信息
            const currentBar = data.kline_data[data.kline_data.length - 1];
            updateCurrentInfo(currentBar, data.progress);

            // 加载交易标记
            updateTradeMarkers(data.trade_markers || []);
        } else {
            // 如果没有K线数据，也视为一种失败
            throw new Error("Initial data received, but kline_data is empty.");
        }

        // 加载技术指标
        await loadTechnicalIndicator(currentIndicatorType);

        updateAccountInfo();
    };

    try {
        // 第一次尝试加载数据
        await attemptToLoad();
    } catch (error) {
        console.error('初次加载初始数据失败:', error);
        console.log('正在尝试自动重置训练并重新加载...');

        try {
            // 自动重置训练
            const resetResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/reset`, {
                method: 'POST'
            });

            if (!resetResponse.ok) {
                // 如果连重置都失败了，那就没有办法了
                throw new Error('自动重置训练失败，无法恢复。');
            }

            console.log('训练已成功重置，正在进行第二次加载尝试...');

            // 清理UI上的旧交易记录
            document.getElementById('trade-history').innerHTML = '<div class="no-trades">暂无交易记录</div>';

            // 第二次尝试加载数据
            await attemptToLoad();

            console.log('第二次加载成功！');

        } catch (finalError) {
            console.error('自动重置或第二次加载失败:', finalError);
            // 只有在重试也失败后，才向用户显示最终的错误提示
            alert('加载数据失败，请尝试重新开始一局训练。');

            // 加载失败后，最好将用户带回到主界面
            resetToMainAppState();
        }
    }
}

function updateCurrentInfo(barData, progress) {
    if (!barData) return;

    const date = new Date(barData.time * 1000);
    const formattedDate = `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
    document.getElementById('current-date').textContent = formattedDate;
    document.getElementById('current-price').textContent = `¥${barData.close.toFixed(2)}`;

    // 显示当前bar ID
    document.getElementById('current-bar-id').textContent = `Bar ID: ${barData.bar_id || 'N/A'}`;

    // 更新当日详情
    document.getElementById('open-price').textContent = `¥${barData.open.toFixed(2)}`;
    document.getElementById('high-price').textContent = `¥${barData.high.toFixed(2)}`;
    document.getElementById('low-price').textContent = `¥${barData.low.toFixed(2)}`;
    document.getElementById('close-price').textContent = `¥${barData.close.toFixed(2)}`;

    // 计算涨跌幅（使用前日收盘价）
    if (progress && progress.current_bar_id > 1) {
        const changePercent = ((barData.close - barData.lastClose) / barData.lastClose * 100).toFixed(2);
        document.getElementById('change-percent').textContent = `${changePercent}%`;
        document.getElementById('change-percent').style.color = changePercent > 0 ? '#ff4d4f' : changePercent < 0 ? '#008000' : '#000000';
    }

    // 更新进度信息
    if (progress) {
        document.getElementById('training-progress').textContent =
            `进度: ${progress.training_progress.toFixed(1)}% (${progress.current_bar_id}/${progress.total_bars - progress.preview_bars})`;
    }
}

// function updateTradeMarkers(markers) {
//     if (!tradeMarkerSeries || !markers) return;
//
//     const markerData = markers.map(marker => ({
//         time: marker.time,
//         position: marker.type === 'B' ? 'aboveBar' : 'belowBar',
//         color: marker.type === 'B' ? '#ff4d4f' : '#008000',
//         shape: marker.type === 'B' ? 'arrowDown' : 'arrowUp',
//         text: marker.type,
//         size: 1
//     }));
//
//     LightweightCharts.createSeriesMarkers(candlestickSeries, markerData);
// }
function updateTradeMarkers(markers) {
    if (!tradeMarkerSeries || !markers) return;

    // 1. 获取所有K线数据并构建一个以时间为键的Map，方便快速查找
    const allCandlestickData = candlestickSeries.data();
    const candlestickMap = new Map();
    allCandlestickData.forEach(data => {
        candlestickMap.set(data.time, data);
    });

    const markerData = markers.map(marker => {
        const klineData = candlestickMap.get(marker.time);
        let shape;

        if (klineData) {
            // 判断K线是涨是跌
            const isKlineUp = klineData.close > klineData.open;

            if (isKlineUp) {
                // 在红K上：箭头朝下 (表示在K线顶部买卖)
                shape = 'arrowDown';
            } else {
                // 平盘K线，默认朝上
                shape = 'arrowUp';
            }

        } else {
            // 如果找不到对应的K线数据，使用默认形状
            shape = marker.type === 'B' ? 'arrowDown' : 'arrowUp';
        }

        return {
            time: marker.time,
            position: shape === 'arrowDown' ? 'aboveBar' : 'belowBar',
            color: marker.type === 'B' ? '#ff4d4f' : '#008000',
            shape: shape,
            text: marker.type,
            size: 1
        };
    });

    LightweightCharts.createSeriesMarkers(candlestickSeries, markerData);
}

// 回放控制
function togglePlayback() {
    if (isPlaying) {
        pausePlayback();
    } else {
        startPlayback();
    }
}

function startPlayback() {
    isPlaying = true;
    document.querySelector('.play-icon').classList.add('hidden');
    document.querySelector('.pause-icon').classList.remove('hidden');

    const speed = parseFloat(document.getElementById('playback-speed').value);
    const interval = speed * 1000;

    playbackInterval = setInterval(nextBar, interval);
}

function pausePlayback() {
    isPlaying = false;
    document.querySelector('.play-icon').classList.remove('hidden');
    document.querySelector('.pause-icon').classList.add('hidden');

    if (playbackInterval) {
        clearInterval(playbackInterval);
        playbackInterval = null;
    }
}

function updatePlaybackSpeed() {
    if (isPlaying) {
        pausePlayback();
        startPlayback();
    }
}

async function nextBar() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/next`, {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();

            if (data.finished) {
                // 训练结束
                pausePlayback();
                showReport(data.report);
            } else {
                // 更新图表数据
                if (data.new_bar) {
                    candlestickSeries.update(data.new_bar);
                    updateAdjustment();

                    // 更新成交量数据，支持颜色
                    if (data.new_volume) {
                        volumeSeries.update(data.new_volume);
                    }

                    updateCurrentInfo(data.new_bar, data.progress);

                    // 更新移动平均线
                    await updateMovingAverages();

                    // 更新技术指标
                    await loadTechnicalIndicator(currentIndicatorType);
                }

                updateAccountInfo();
            }
        } else {
            const error = await response.json();
            console.error('获取下一根K线失败:', error);
        }
    } catch (error) {
        console.error('获取下一根K线失败:', error);
    }
}

async function updateMovingAverages() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data`);
        const data = await response.json();

        if (data.ma_data) {
            // 只更新最新的数据点
            maPeriods.forEach(p => {
                const mData = data.ma_data[p];
                if (maSeries[p] && mData && mData.length > 0) {
                    maSeries[p].update(mData[mData.length - 1]);
                }
            });
        }
    } catch (error) {
        console.error('更新移动平均线失败:', error);
    }
}

async function loadTechnicalIndicator(indicatorType) {
    const visibleLogicalRange = chart.timeScale().getVisibleLogicalRange();
    try {
        // 获取DOM元素，并检查是否存在
        const indicatorChartElement = document.getElementById('indicator-chart');
        const indicatorHeaderElement = document.getElementById('indicator-header');

        // 如果之前显示的是BOLL，先移除主图上的BOLL线
        if (bollSeries.upper) {
            chart.removeSeries(bollSeries.upper);
            chart.removeSeries(bollSeries.middle);
            chart.removeSeries(bollSeries.lower);
            bollSeries = {}; // 清空

            // 立即清除界面残留的 BOLL 标签
            const bollInfoEl = document.getElementById('boll-info-content');
            if (bollInfoEl) {
                bollInfoEl.remove();
            }
            
            renderChartLegend();
        }

        // 清除下方指标图表的所有现有系列
        if (currentIndicatorSeries.length > 0) {
            currentIndicatorSeries.forEach(series => indicatorChart.removeSeries(series));
            currentIndicatorSeries = []; // 清空数组
        }

        if (indicatorChartElement) {
            indicatorChartElement.style.display = (indicatorType === 'BOLL') ? 'none' : 'block';
        }
        if (indicatorHeaderElement) {
            indicatorHeaderElement.style.display = 'block'; // 确保选择器总是可见
        }

        // 如果选择的是BOLL，则直接在主图上绘制并返回
        if (indicatorType === 'BOLL') {
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/indicators/BOLL`);
            const data = await response.json();
            if (data.type === 'BOLL' && data.data) {
                const upperData = data.data.map(item => ({ time: item.time, value: item.upper }));
                const middleData = data.data.map(item => ({ time: item.time, value: item.middle }));
                const lowerData = data.data.map(item => ({ time: item.time, value: item.lower }));

                // 在主图表(chart)上添加BOLL线
                bollSeries.upper = chart.addSeries(LightweightCharts.LineSeries, {
                    color: '#ff6b6b',
                    lineWidth: 2,
                    priceLineVisible: false,
                    crosshairMarkerVisible: false,
                    lastValueVisible: false
                });
                bollSeries.middle = chart.addSeries(LightweightCharts.LineSeries, {
                    color: '#4ecdc4',
                    lineWidth: 2,
                    priceLineVisible: false,
                    crosshairMarkerVisible: false,
                    lastValueVisible: false
                });
                bollSeries.lower = chart.addSeries(LightweightCharts.LineSeries, {
                    color: '#45b7d1',
                    lineWidth: 2,
                    priceLineVisible: false,
                    crosshairMarkerVisible: false,
                    lastValueVisible: false
                });

                bollSeries.upper.setData(upperData);
                bollSeries.middle.setData(middleData);
                bollSeries.lower.setData(lowerData);
                renderChartLegend();
            }
        } else {
            // --- 如果不是BOLL，则按原逻辑在下方图表绘制 ---
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/indicators/${indicatorType}`);
            const data = await response.json();

            // 根据指标类型创建新的系列 (此部分代码保持不变)
            if (data.type === 'MACD' && data.data) {
                const difData = data.data.map(item => ({ time: item.time, value: item.dif }));
                const deaData = data.data.map(item => ({ time: item.time, value: item.dea }));
                const histogramData = data.data.map(item => ({
                    time: item.time,
                    value: item.histogram,
                    color: item.histogram >= 0 ? '#ff4d4f' : '#008000'
                }));

                const difSeries = indicatorChart.addSeries(LightweightCharts.LineSeries, {
                    color: '#ff6b6b',
                    lineWidth: 1,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false
                });
                const deaSeries = indicatorChart.addSeries(LightweightCharts.LineSeries, {
                    color: '#4ecdc4',
                    lineWidth: 1,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false
                });
                const histogramSeries = indicatorChart.addSeries(LightweightCharts.HistogramSeries, {
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false
                });
                difSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
                deaSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
                histogramSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });

                currentIndicatorSeries.push(difSeries, deaSeries, histogramSeries);

                difSeries.setData(difData);
                deaSeries.setData(deaData);
                histogramSeries.setData(histogramData);
                renderIndicatorLegend();

            } else if (data.type === 'RSI' && data.data && data.periods) {
                const rsiColors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9c74f', '#90be6d', '#f8961e'];
                data.periods.forEach((period, index) => {
                    const rsiData = data.data.map(item => ({ time: item.time, value: item[`rsi${period}`] }));
                    const rsiSeries = indicatorChart.addSeries(LightweightCharts.LineSeries, {
                        color: rsiColors[index % rsiColors.length],
                        lineWidth: 1,
                        crosshairMarkerVisible: false,
                        priceLineVisible: false,
                        lastValueVisible: false,
                    });
                    rsiSeries.rsiTitle = `RSI(${period})`;
                    currentIndicatorSeries.push(rsiSeries);
                    rsiSeries.setData(rsiData);
                    rsiSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
                });
                renderIndicatorLegend();

            } else if (data.type === 'KDJ' && data.data) {
                const kData = data.data.map(item => ({ time: item.time, value: item.k }));
                const dData = data.data.map(item => ({ time: item.time, value: item.d }));
                const jData = data.data.map(item => ({ time: item.time, value: item.j }));

                const kSeries = indicatorChart.addSeries(LightweightCharts.LineSeries, {
                    color: '#ff6b6b',
                    lineWidth: 1,
                    crosshairMarkerVisible: false
                });
                const dSeries = indicatorChart.addSeries(LightweightCharts.LineSeries, {
                    color: '#4ecdc4',
                    lineWidth: 1,
                    crosshairMarkerVisible: false
                });
                const jSeries = indicatorChart.addSeries(LightweightCharts.LineSeries, {
                    color: '#45b7d1',
                    lineWidth: 1,
                    crosshairMarkerVisible: false
                });
                kSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
                dSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
                jSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });

                currentIndicatorSeries.push(kSeries, dSeries, jSeries);
                kSeries.setData(kData);
                dSeries.setData(dData);
                jSeries.setData(jData);
                renderIndicatorLegend();
            }
        }

    } catch (error) {
        console.error(`加载技术指标失败: ${error}`);
    } finally {
        // 2. 恢复之前保存的可见逻辑范围
        // 只有在范围有效时才恢复
        if (visibleLogicalRange !== null) {
            indicatorChart.timeScale().setVisibleLogicalRange(visibleLogicalRange);
        }
    }
}

function changeIndicator() {
    const select = document.getElementById('indicator-select');
    currentIndicatorType = select.value;
    loadTechnicalIndicator(currentIndicatorType);
}

// 复权设置
async function updateAdjustment() {
    const adjustment = document.querySelector('input[name="adjustment"]:checked').value;

    const maQuery = maPeriods.join(',');
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/adjustment?ma_periods=${maQuery}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ adjustment })
        });

        if (response.ok) {
            const data = await response.json();
            // 重新加载图表数据
            candlestickSeries.setData(data.kline_data);

            // 重新加载成交量数据，支持颜色
            if (data.volume_data) {
                volumeSeries.setData(data.volume_data);
            }

            // 重新加载移动平均线
            if (data.ma_data) {
                maPeriods.forEach(p => {
                    if (maSeries[p]) {
                        maSeries[p].setData(data.ma_data[p] || []);
                    }
                });
            }
            renderChartLegend();
        }
    } catch (error) {
        console.error('更新复权设置失败:', error);
    }
}

// 交易操作
function limitTradeQuantity() {
    const input = document.getElementById('trade-quantity');
    // const maxQuantity = parseInt(document.getElementById('max-quantity').textContent) || 0;

    // if (parseInt(input.value) > maxQuantity) {
    //     input.value = maxQuantity;
    // }
    if (parseInt(input.value) > input.max) {
        input.value = input.max;
    }
}

async function executeBuy() {
    const quantity = parseInt(document.getElementById('trade-quantity').value);
    if (!quantity || quantity <= 0) {
        alert('请输入有效的交易数量');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/trade`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'buy',
                quantity: quantity
            })
        });

        if (response.ok) {
            const result = await response.json();
            updateAccountInfo();
            addTradeRecord(result.trade);
            updateTradeMarkers(result.trade_markers);
        } else {
            const error = await response.json();
            alert(error.message || '买入失败');
        }
    } catch (error) {
        console.error('买入失败:', error);
        alert('买入失败');
    }
}

async function executeSell() {
    const quantity = parseInt(document.getElementById('trade-quantity').value);
    if (!quantity || quantity <= 0) {
        alert('请输入有效的交易数量');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/trade`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'sell',
                quantity: quantity
            })
        });

        if (response.ok) {
            const result = await response.json();
            updateAccountInfo();
            addTradeRecord(result.trade);
            updateTradeMarkers(result.trade_markers);
        } else {
            const error = await response.json();
            alert(error.message || '卖出失败');
        }
    } catch (error) {
        console.error('卖出失败:', error);
        alert('卖出失败');
    }
}

// 账户信息更新
async function updateAccountInfo() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/account`);
        const account = await response.json();

        document.getElementById('total-assets').textContent = `¥${account.total_assets.toLocaleString()}`;
        document.getElementById('available-cash').textContent = `¥${account.available_cash.toLocaleString()}`;
        document.getElementById('position-value').textContent = `¥${account.position_value.toLocaleString()}`;
        document.getElementById('floating-pnl').textContent = `¥${account.floating_pnl.toLocaleString()}`;
        document.getElementById('floating-pnl').style.color = account.floating_pnl > 0 ? '#ff4d4f' : account.floating_pnl < 0 ? '#008000' : '#000000';

        // 更新最大可交易数量
        document.getElementById('max-buy-quantity').textContent = account.max_buyable_quantity;
        if (account.position_summary) {
            let max_sell_qty = account.position_summary.available_shares / 100
            document.getElementById('max-sell-quantity').textContent = max_sell_qty;
            document.getElementById('trade-quantity').max = Math.max(account.max_buyable_quantity, max_sell_qty);
        }
        else {
            document.getElementById('max-sell-quantity').textContent = '0';
            document.getElementById('trade-quantity').max = account.max_buyable_quantity;
        }

        // 更新持仓信息
        updatePositionInfo(account.position_summary);

    } catch (error) {
        console.error('更新账户信息失败:', error);
    }
}

// 自动同步状态
function startAutoSync() {
    if (autoSyncInterval) clearInterval(autoSyncInterval);
    lastKnownBarId = null;
    lastKnownTradeCount = null;

    autoSyncInterval = setInterval(async () => {
        if (!currentTraining || isPlaying) return;

        const isTrainingInterfaceVisible = !document.getElementById('training-interface').classList.contains('hidden');
        if (!isTrainingInterfaceVisible) return;

        try {
            const resp = await fetch(`${API_BASE}/training/${currentTraining.id}/sync_status`);
            if (resp.status === 404) {
                stopAutoSync();
                return;
            }
            if (resp.ok) {
                const data = await resp.json();
                let needsRefresh = false;

                if (lastKnownBarId !== null && data.current_bar_id !== lastKnownBarId) {
                    needsRefresh = true;
                }
                if (lastKnownTradeCount !== null && data.trade_markers_count !== lastKnownTradeCount) {
                    needsRefresh = true;
                }

                if (needsRefresh) {
                    await loadInitialData();
                }

                lastKnownBarId = data.current_bar_id;
                lastKnownTradeCount = data.trade_markers_count;
            }
        } catch (e) { }
    }, 500);
}

function stopAutoSync() {
    if (autoSyncInterval) {
        clearInterval(autoSyncInterval);
        autoSyncInterval = null;
    }
}

function updatePositionInfo(positionSummary) {
    const container = document.getElementById('current-positions');

    if (!positionSummary || positionSummary.total_shares === 0) {
        container.innerHTML = '<div class="no-positions">暂无持仓</div>';
        return;
    }

    container.innerHTML = `
        <div class="position-summary">
            <div class="position-item">
                <span>总持股:</span>
                <span>${(positionSummary.total_shares / 100).toFixed(2).toLocaleString()} 手</span>
            </div>
            <div class="position-item">
                <span>可卖:</span>
                <span>${(positionSummary.available_shares / 100).toFixed(2).toLocaleString()} 手</span>
            </div>
            <div class="position-item">
                <span>成本价:</span>
                <span>¥${positionSummary.average_cost.toFixed(2)}</span>
            </div>
            <div class="position-item">
                <span>现价:</span>
                <span>¥${positionSummary.current_price.toFixed(2)}</span>
            </div>
            <div class="position-item">
                <span>盈亏:</span>
                <span class="${positionSummary.pnl_percent >= 0 ? 'positive' : 'negative'}">${positionSummary.pnl_percent.toFixed(2)}%</span>
            </div>
        </div>
    `;
}

function addTradeRecord(trade) {
    const container = document.getElementById('trade-history');

    // 如果是第一条记录，清除"暂无交易记录"
    if (container.querySelector('.no-trades')) {
        container.innerHTML = '';
    }

    const tradeItem = document.createElement('div');
    tradeItem.className = `trade-item ${trade.action}`;
    tradeItem.innerHTML = `
        <div class="trade-header">
            <span class="trade-action">${trade.action === 'buy' ? '买入' : '卖出'}</span>
            <span class="trade-time">${trade.trade_date}</span>
        </div>
        <div class="trade-details">
            <div>Bar ID: ${trade.bar_id}</div>
            <div>数量: ${trade.quantity} 手</div>
            <div>价格: ¥${trade.price.toFixed(2)}</div>
            <div>金额: ¥${trade.net_amount.toFixed(2)}</div>
        </div>
    `;

    // 插入到顶部
    container.insertBefore(tradeItem, container.firstChild);

    // 限制显示的记录数量
    const items = container.querySelectorAll('.trade-item');
    if (items.length > 10) {
        container.removeChild(items[items.length - 1]);
    }
}

// 训练控制

/**
 * 强制平仓函数
 * 会持续尝试卖出所有持仓，直到持仓清空。
 * 如果当天有T+1限制，会自动进入下一天再尝试。
 * @returns {Promise<boolean>} - 返回一个Promise，成功清仓则resolve(true)，否则resolve(false)。
 */
async function forceLiquidatePosition() {
    console.log("开始执行强制平仓流程...");

    // 设置一个最大尝试天数，防止无限循环
    const maxAttempts = 10;
    let attempts = 0;

    while (attempts < maxAttempts) {
        try {
            // 1. 获取最新的账户信息
            const accountResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/account`);
            if (!accountResponse.ok) {
                alert('强制平仓失败：无法获取账户信息。');
                return false;
            }
            const account = await accountResponse.json();

            const totalShares = account.position_summary?.total_shares || 0;
            const availableShares = account.position_summary?.available_shares || 0;

            // 2. 如果持仓已清空，则成功退出循环
            if (totalShares === 0) {
                console.log("持仓已全部清空。");
                return true;
            }

            // 3. 如果有可卖的股票，就卖掉它们
            if (availableShares > 0) {
                console.log(`检测到可卖持仓 ${availableShares} 股，正在执行卖出...`);
                const sellQuantity = Math.floor(availableShares / 100); // 转换为“手”

                const sellResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/trade`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'sell', quantity: sellQuantity })
                });

                if (!sellResponse.ok) {
                    const error = await sellResponse.json();
                    alert(`强制卖出部分持仓失败: ${error.message}`);
                    return false;
                }

                const result = await sellResponse.json();
                updateAccountInfo();
                addTradeRecord(result.trade);
                updateTradeMarkers(result.trade_markers);
                console.log(`成功卖出 ${sellQuantity} 手。`);

                // 卖出后再次检查，如果已经全部卖完，直接成功返回
                if (account.position_summary.total_shares - availableShares === 0) {
                    console.log("持仓已全部清空。");
                    return true;
                }
            }

            // 4. 如果还有持仓但当天不可卖，则进入下一天
            console.log("当天有T+1限制或已无更多可卖股票，进入下一个交易日...");
            await nextBar(); // 调用 nextBar 进入下一天

            // 增加一个小的延时，等待UI和后端状态更新
            await new Promise(resolve => setTimeout(resolve, 100));

        } catch (error) {
            console.error('强制平仓过程中发生错误:', error);
            alert('强制平仓过程中发生错误，请检查控制台。');
            return false;
        }
        attempts++;
    }

    alert('强制平仓失败：已超过最大尝试天数，仍有持仓未卖出。');
    return false;
}

async function endTraining() {
    // 1. 首先获取当前账户状态，检查是否有持仓
    const accountResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/account`);
    if (!accountResponse.ok) {
        alert('无法获取账户信息，结束训练失败。');
        return;
    }
    const account = await accountResponse.json();
    const hasPosition = account.position_summary?.total_shares > 0;

    // 2. 如果有持仓，进行二次确认
    if (hasPosition) {
        if (!confirm('您当前仍有持仓，系统将自动为您强制平仓。确定要结束训练吗？')) {
            return; // 用户取消，则不执行任何操作
        }

        // 用户确认，开始强制平仓流程
        const liquidationSuccess = await forceLiquidatePosition();

        // 如果平仓失败，则中止结束流程
        if (!liquidationSuccess) {
            alert('自动平仓失败，无法结束训练。请手动处理或重置训练。');
            return;
        }
    }
    // 如果没有持仓，或者平仓成功后，继续执行原来的结束逻辑
    else {
        // 对于没有持仓的情况，也进行一次确认
        if (!confirm('确定要结束当前训练吗？')) {
            return;
        }
    }

    // 3. 所有持仓已清空，正式调用后端的 end 接口
    try {
        console.log("所有持仓已清空，正在生成最终报告...");
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/end`, {
            method: 'POST'
        });

        if (response.ok) {
            const report = await response.json();
            pausePlayback();
            showReport(report);
        } else {
            const error = await response.json();
            alert(`结束训练失败: ${error.message}`);
        }
    } catch (error) {
        console.error('结束训练失败:', error);
        alert('结束训练失败');
    }
}

async function resetTraining() {
    if (!confirm('确定要重置当前训练吗？所有交易记录将被清除。')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/reset`, {
            method: 'POST'
        });

        if (response.ok) {
            pausePlayback();
            await loadInitialData();

            // 清除交易记录显示
            document.getElementById('trade-history').innerHTML = '<div class="no-trades">暂无交易记录</div>';
        }
    } catch (error) {
        console.error('重置训练失败:', error);
        alert('重置训练失败');
    }
}

/**
 * 更新报告摘要区域的辅助函数
 * @param {HTMLElement} parentElement - 父容器元素
 * @param {object} report - 报告数据对象
 */
function updateReportSummary(parentElement, report) {
    // 使用 Map 定义标签和对应的值，更易于管理
    const summaryItems = new Map([
        ['股票代码:', report.stock_code],
        ['训练期间:', `${report.start_date} 至 ${report.end_date}`],
        ['初始资金:', `¥${report.initial_capital.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`],
        ['最终资产:', `¥${report.final_capital.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`],
        ['总交易次数:', `${report.total_trades} 次`],
        ['交易胜率:', `${(report.trade_win_rate || 0).toFixed(2)}%`]
    ]);

    parentElement.innerHTML = `
        <h3>训练总结</h3>
        <div class="summary-grid"></div>
    `;
    const grid = parentElement.querySelector('.summary-grid');

    // 循环创建摘要项
    summaryItems.forEach((value, label) => {
        const item = document.createElement('div');
        item.className = 'summary-item';
        item.innerHTML = `<span class="label">${label}</span><span class="value">${value}</span>`;
        grid.appendChild(item);
    });

    // 处理需要额外逻辑的摘要项
    const totalReturnItem = document.createElement('div');
    totalReturnItem.className = 'summary-item';
    totalReturnItem.innerHTML = `
        <span class="label">总收益率:</span>
        <span class="value ${report.total_return >= 0 ? 'positive' : 'negative'}">
            ${report.total_return.toFixed(2)}%
        </span>`;
    grid.appendChild(totalReturnItem);
}


/**
 * 创建并填充交易明细表格的辅助函数
 * @param {HTMLElement} parentElement - 父容器元素
 * @param {Array} tradeDetails - 交易明细数组
 */
function createTradeDetailsTable(parentElement, tradeDetails) {
    parentElement.innerHTML = `
        <h3>交易明细</h3>
        <div class="trade-details-table">
            <table>
                <thead>
                    <tr>
                        <th>Bar</th>
                        <th>日期</th>
                        <th>操作</th>
                        <th>价格</th>
                        <th>数量</th>
                        <th>金额</th>
                        <th>税费</th>
                        <th>净金额</th>
                    </tr>
                </thead>
                <tbody></tbody>
                <tfoot></tfoot>
            </table>
        </div>
    `;

    const tbody = parentElement.querySelector('tbody');
    const tfoot = parentElement.querySelector('tfoot');

    // 初始化合计数据
    const totals = {
        totalAmount: 0,
        totalCommission: 0,
        totalProfit: 0,
    };

    // 动态创建表格行
    tradeDetails.forEach(trade => {
        const row = tbody.insertRow(); // 创建新行

        const isBuy = trade.action === 'buy';
        const totalFee = trade.commission + trade.stamp_tax;
        const profit = isBuy ? -(trade.amount + totalFee) : (trade.amount - totalFee);

        // 填充单元格
        row.innerHTML = `
            <td>${trade.bar_id}</td>
            <td>${trade.date}</td>
            <td class="${trade.action}">${isBuy ? '买入' : '卖出'}</td>
            <td>¥${trade.price.toFixed(2)}</td>
            <td>${trade.quantity}</td>
            <td>${isBuy ? '-' : ''}¥${trade.amount.toFixed(2)}</td>
            <td>-¥${totalFee.toFixed(2)}</td>
            <td>${profit >= 0 ? '¥' : '-¥'}${Math.abs(profit).toFixed(2)}</td>
        `;

        // 累加合计值
        if (!isBuy) {
            totals.totalAmount += trade.amount;
        }
        else {
            totals.totalAmount -= trade.amount;
        }
        totals.totalProfit += profit;
        totals.totalCommission += totalFee;
    });

    // 创建并插入合计行
    const totalRow = tfoot.insertRow();
    totalRow.className = 'total-row'; // 添加样式类以便高亮
    totalRow.innerHTML = `
        <td colspan="5"><strong>合计</strong></td>
        <td><strong>¥${totals.totalAmount.toFixed(2)}</strong></td>
        <td><strong>-¥${totals.totalCommission.toFixed(2)}</strong></td>
        <td><strong>${totals.totalProfit >= 0 ? '¥' : '-¥'}${Math.abs(totals.totalProfit).toFixed(2)}</strong></td>
    `;
}


/**
 * 请求 AI 智能复盘点评
 */
async function requestAIAnalysis() {
    const aiBtn = document.getElementById('ai-analyze-btn');
    const originalText = aiBtn.innerHTML;
    
    try {
        aiBtn.disabled = true;
        aiBtn.innerHTML = '⏳ 正在请求AI分析，请稍候...';
        
        const response = await fetch(`${API_BASE}/training/analyze_report`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                report: currentReportData,
                user: currentUser
            })
        });

        if (response.ok) {
            const result = await response.json();
            
            // Render the AI commentary
            const reportContent = document.getElementById('report-content');
            
            // Check if section already exists
            let aiSection = document.querySelector('.ai-commentary-section');
            if (!aiSection) {
                aiSection = document.createElement('div');
                aiSection.className = 'ai-commentary-section';
                // Insert after summary but before details
                const detailsSection = document.querySelector('.trade-details-section');
                if (detailsSection) {
                    reportContent.insertBefore(aiSection, detailsSection);
                } else {
                    reportContent.appendChild(aiSection);
                }
            }
            
            // Format markdown using marked.js if available, otherwise simple formatting
            let formattedContent = '';
            if (typeof marked !== 'undefined') {
                formattedContent = marked.parse(result.ai_commentary);
            } else {
                formattedContent = result.ai_commentary.replace(/\n/g, '<br>');
            }
            
            aiSection.innerHTML = `
                <h3>🤖 AI 复盘点评</h3>
                <div class="ai-content">${formattedContent}</div>
            `;
            
            // Scroll to the AI section
            aiSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Hide the button since we got the result
            aiBtn.classList.add('hidden');
        } else {
            const error = await response.json();
            alert(`AI 分析失败: ${error.error || '未知错误'}`);
        }
    } catch (error) {
        console.error('AI 分析请求失败:', error);
        alert('网络请求失败，请检查服务连接。');
    } finally {
        aiBtn.disabled = false;
        aiBtn.innerHTML = originalText;
    }
}

// 内部变量用于存储当前报告数据
let currentReportData = null;

/**
 * 主函数：显示完整的报告界面
 * @param {object} report - 包含所有报告数据的对象
 */
function showReport(report) {
    // 保存当前报告数据供 AI 分析使用
    currentReportData = report;
    
    // 切换界面可见性
    document.getElementById('training-interface').classList.add('hidden');
    document.getElementById('report-interface').classList.remove('hidden');

    // 恢复工具栏状态
    toggleToolbarForTraining(false);

    // 获取报告内容的容器
    const reportContent = document.getElementById('report-content');
    reportContent.innerHTML = ''; // 清空旧内容

    // 检查用户是否开启了 AI API
    checkAIStatusAndShowButton();

    // 创建并添加摘要和交易详情
    const summarySection = document.createElement('div');
    summarySection.className = 'report-summary';
    updateReportSummary(summarySection, report); // 使用辅助函数填充摘要

    const detailsSection = document.createElement('div');
    detailsSection.className = 'trade-details-section';
    createTradeDetailsTable(detailsSection, report.trade_details); // 使用辅助函数创建表格

    // 将生成好的模块添加到主容器中
    reportContent.appendChild(summarySection);

    reportContent.appendChild(detailsSection);

    // 更新用户统计
    loadUserStatistics();
}

/**
 * 检查AI状态并显示/隐藏AI分析按钮
 */
async function checkAIStatusAndShowButton() {
    const aiBtn = document.getElementById('ai-analyze-btn');
    if (!currentUser || !aiBtn) return;
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/settings`);
        if (response.ok) {
            const settings = await response.json();
            if (settings.enable_ai_api) {
                aiBtn.classList.remove('hidden');
            } else {
                aiBtn.classList.add('hidden');
            }
        }
    } catch (e) {
        console.error('Failed to check AI status:', e);
    }
}

async function viewFullChart() {
    if (!currentTraining && !currentReportData) {
        alert('找不到训练会话数据，无法查看完整走势');
        return;
    }
    
    // Use session_id from report data if available, otherwise from currentTraining
    const trainingId = currentReportData ? currentReportData.session_id : currentTraining.id;

    const maQuery = maPeriods.join(',');
    try {
        const response = await fetch(`${API_BASE}/training/${trainingId}/full_data?ma_periods=${maQuery}`);
        if (!response.ok) {
            throw new Error('获取完整数据失败');
        }
        
        const data = await response.json();
        
        // Hide report interface and show training interface
        document.getElementById('report-interface').classList.add('hidden');
        document.getElementById('training-interface').classList.remove('hidden');
        
        // Set view-only mode visually
        document.querySelectorAll('.trade-controls button').forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
        });
        
        const endBtn = document.getElementById('end-training-btn');
        if (endBtn) {
            endBtn.disabled = true;
            endBtn.style.opacity = '0.5';
        }

        const nextBarBtn = document.getElementById('next-bar-btn');
        if (nextBarBtn) {
            nextBarBtn.disabled = true;
            nextBarBtn.style.opacity = '0.5';
        }
        
        const playPauseBtn = document.getElementById('play-pause-btn');
        if (playPauseBtn) {
            playPauseBtn.disabled = true;
            playPauseBtn.style.opacity = '0.5';
        }
        
        // Update chart data
        if (data.kline_data && data.kline_data.length > 0) {
            candlestickSeries.setData(data.kline_data);
            volumeSeries.setData(data.volume_data);

            if (data.ma_data) {
                maPeriods.forEach(p => {
                    if (maSeries[p]) {
                        maSeries[p].setData(data.ma_data[p] || []);
                    }
                });
            }
            
            updateTradeMarkers(data.trade_markers || []);
            
            // Re-load technical indicators for full range
            await loadTechnicalIndicator(currentIndicatorType);
            
            // Adjust time scale to fit all data
            chart.timeScale().fitContent();
        }
        
        // Disable global shortcuts for view-only mode
        isViewOnlyMode = true;
        
        // Add a back to report button if it doesn't exist
        let backBtn = document.getElementById('back-to-report-btn');
        if (!backBtn) {
            backBtn = document.createElement('button');
            backBtn.id = 'back-to-report-btn';
            backBtn.className = 'btn btn-primary';
            backBtn.style.width = '100%';
            backBtn.style.marginTop = '10px';
            backBtn.textContent = '返回复盘报告';
            backBtn.onclick = () => {
                document.getElementById('training-interface').classList.add('hidden');
                document.getElementById('report-interface').classList.remove('hidden');
            };
            
            // Add it to the training controls section
            const controlsSection = document.querySelector('.training-controls');
            if (controlsSection) {
                controlsSection.appendChild(backBtn);
            }
        }
        backBtn.classList.remove('hidden');
        
    } catch (error) {
        console.error('查看完整走势失败:', error);
        alert('获取完整走势数据失败');
    }
}

// 内部变量用于跟踪是否为只读模式
let isViewOnlyMode = false;

// 工具函数
function formatNumber(num) {
    return num.toLocaleString();
}

function formatCurrency(num) {
    return `¥${num.toLocaleString()}`;
}

function formatPercent(num) {
    return `${num.toFixed(2)}%`;
}
