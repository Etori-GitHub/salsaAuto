// salsaAuto Web UI

// === 工具函数 ===

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return { error: true, message: error.message };
    }
}

// === 首页 ===

async function loadStatus() {
    const data = await fetchAPI('/api/status');
    
    const statusBar = document.getElementById('status-bar');
    if (statusBar) {
        statusBar.innerHTML = `
            <span class="status-item ${data.token_loaded ? 'success' : 'warning'}">
                Token: ${data.token_loaded ? 'OK' : 'X'}
            </span>
            <span class="status-item">
                会员: ${data.member_count} 人
            </span>
        `;
    }
    
    const tokenStatus = document.getElementById('token-status');
    if (tokenStatus) {
        tokenStatus.textContent = data.token_loaded ? '已加载' : '未加载';
        tokenStatus.parentElement.classList.toggle('success', data.token_loaded);
    }
    
    const memberCount = document.getElementById('member-count');
    if (memberCount) {
        memberCount.textContent = data.member_count;
    }
}

async function loadStoreCount() {
    const data = await fetchAPI('/api/stores');
    const el = document.getElementById('store-count');
    if (el) el.textContent = Object.keys(data.stores || {}).length;
}

async function loadDishCount() {
    const data = await fetchAPI('/api/dishes');
    const el = document.getElementById('dish-count');
    if (el) el.textContent = Object.keys(data.dishes || {}).length;
}

// === 门店 ===

async function loadStoresTable() {
    const data = await fetchAPI('/api/stores');
    const tbody = document.getElementById('store-list');
    if (!tbody) return;
    
    const stores = data.stores || {};
    if (Object.keys(stores).length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" class="loading">暂无数据</td></tr>';
        return;
    }
    
    tbody.innerHTML = Object.entries(stores).map(([id, store]) => `
        <tr>
            <td>${id}</td>
            <td>${store.name}</td>
        </tr>
    `).join('');
}

async function loadStores() {
    const data = await fetchAPI('/api/stores');
    const stores = data.stores || {};
    
    document.querySelectorAll('select[id$="-store"]').forEach(select => {
        select.innerHTML = Object.entries(stores).map(([id, store]) => 
            `<option value="${id}">${store.name}</option>`
        ).join('');
    });
}

// === 菜品 ===

async function loadDishesTable() {
    const data = await fetchAPI('/api/dishes');
    const tbody = document.getElementById('dish-list');
    if (!tbody) return;
    
    const dishes = data.dishes || {};
    if (Object.keys(dishes).length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="loading">暂无数据</td></tr>';
        return;
    }
    
    tbody.innerHTML = Object.entries(dishes).map(([id, dish]) => `
        <tr>
            <td>${id}</td>
            <td>${dish.name}</td>
            <td>Y${dish.price}</td>
        </tr>
    `).join('');
}

async function loadDishes() {
    const data = await fetchAPI('/api/dishes');
    const dishes = data.dishes || {};
    
    document.querySelectorAll('select[id$="-dish"]').forEach(select => {
        select.innerHTML = Object.entries(dishes).map(([id, dish]) => 
            `<option value="${id}">${dish.name} (Y${dish.price})</option>`
        ).join('');
    });
}

// === 会员 ===

let allMembers = {};

async function loadMembers() {
    const data = await fetchAPI('/api/members');
    allMembers = data.members || {};
    renderMembers(allMembers);
}

function renderMembers(members) {
    const tbody = document.getElementById('member-list');
    if (!tbody) return;
    
    if (Object.keys(members).length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">暂无数据</td></tr>';
        return;
    }
    
    tbody.innerHTML = Object.entries(members).map(([id, member]) => `
        <tr>
            <td>${id}</td>
            <td>${member.username || '-'}</td>
            <td>${member.phone || '-'}</td>
            <td>Y${member.balance || 0}</td>
            <td>
                <span class="type-tag ${member.type === 'yizhiman' ? 'yizhiman' : 'none'}">
                    ${member.type === 'yizhiman' ? '一纸满' : '通用'}
                </span>
            </td>
            <td>
                <button class="btn btn-secondary" onclick="changeMemberType('${id}', '${member.type || 'None'}')">
                    修改类型
                </button>
            </td>
        </tr>
    `).join('');
}

function filterMembers() {
    const typeFilter = document.getElementById('type-filter')?.value || '';
    const search = document.getElementById('search-input')?.value.toLowerCase() || '';
    
    const filtered = Object.fromEntries(
        Object.entries(allMembers).filter(([id, m]) => {
            const matchType = !typeFilter || (m.type || 'None') === typeFilter;
            const matchSearch = !search || 
                (m.username || '').toLowerCase().includes(search) ||
                (m.phone || '').includes(search) ||
                id.includes(search);
            return matchType && matchSearch;
        })
    );
    
    renderMembers(filtered);
}

async function syncMembers() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '同步中...';
    
    const result = await fetchAPI('/api/members/sync', { method: 'POST' });
    
    btn.disabled = false;
    btn.textContent = '同步余额';
    
    if (result.success) {
        alert('同步成功');
        loadMembers();
    } else {
        alert('同步失败: ' + result.message);
    }
}

async function changeMemberType(memberId, currentType) {
    const newType = currentType === 'yizhiman' ? 'None' : 'yizhiman';
    
    if (!confirm(`确定将会员 ${memberId} 的类型改为 ${newType === 'yizhiman' ? '一纸满' : '通用'}？`)) {
        return;
    }
    
    const formData = new FormData();
    formData.append('type', newType);
    
    const result = await fetchAPI(`/api/members/${memberId}/type`, {
        method: 'POST',
        body: formData
    });
    
    if (result.success) {
        loadMembers();
    } else {
        alert('修改失败');
    }
}

// === 订单 ===

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.onclick.toString().includes(tabName));
    });
    
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });
}

// 单个订单
document.getElementById('single-order-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const storeId = document.getElementById('single-store').value;
    const dishId = document.getElementById('single-dish').value;
    const quantity = document.getElementById('single-quantity').value;
    const payType = document.getElementById('single-pay-type').value;
    
    const formData = new FormData();
    formData.append('store_id', storeId);
    formData.append('dish_id', dishId);
    formData.append('quantity', quantity);
    formData.append('pay_type', payType);
    formData.append('member_type', storeId === '32' ? 'yizhiman' : 'None');
    
    const result = await fetchAPI('/api/orders/create', {
        method: 'POST',
        body: formData
    });
    
    alert(result.success ? '创建成功' : '创建失败: ' + result.message);
});

// 按金额刷单
document.getElementById('amount-order-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const storeId = document.getElementById('amount-store').value;
    const dishId = document.getElementById('amount-dish').value;
    const totalAmount = document.getElementById('amount-total').value;
    const payType = document.getElementById('amount-pay-type').value;
    
    if (!confirm(`确定开始刷单？总金额: Y${totalAmount}`)) return;
    
    const formData = new FormData();
    formData.append('store_id', storeId);
    formData.append('dish_id', dishId);
    formData.append('total_amount', totalAmount);
    formData.append('pay_type', payType);
    formData.append('member_type', storeId === '32' ? 'yizhiman' : 'None');
    
    const result = await fetchAPI('/api/orders/batch/amount', {
        method: 'POST',
        body: formData
    });
    
    alert(result.success ? `刷单完成，共 ${result.order_count} 个订单` : '刷单失败');
});

// 按数量刷单
document.getElementById('quantity-order-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const storeId = document.getElementById('quantity-store').value;
    const dishId = document.getElementById('quantity-dish').value;
    const totalQuantity = document.getElementById('quantity-total').value;
    const payType = document.getElementById('quantity-pay-type').value;
    
    if (!confirm(`确定开始刷单？总数量: ${totalQuantity}`)) return;
    
    const formData = new FormData();
    formData.append('store_id', storeId);
    formData.append('dish_id', dishId);
    formData.append('total_quantity', totalQuantity);
    formData.append('pay_type', payType);
    formData.append('member_type', storeId === '32' ? 'yizhiman' : 'None');
    
    const result = await fetchAPI('/api/orders/batch/quantity', {
        method: 'POST',
        body: formData
    });
    
    alert(result.success ? `刷单完成，共 ${result.order_count} 个订单` : '刷单失败');
});

// 一纸满刷单
document.getElementById('yizhiman-order-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const dishId = document.getElementById('yizhiman-dish').value;
    const quantity = document.getElementById('yizhiman-quantity').value;
    const payType = document.getElementById('yizhiman-pay-type').value;
    const orderTime = document.getElementById('yizhiman-time').value;
    const remark = document.getElementById('yizhiman-remark').value;
    
    if (!confirm(`确定开始一纸满刷单？数量: ${quantity}`)) return;
    
    const formData = new FormData();
    formData.append('store_id', '32');
    formData.append('dish_id', dishId);
    formData.append('total_quantity', quantity);
    formData.append('pay_type', payType);
    formData.append('member_type', payType === 'memberPay' ? 'yizhiman' : 'None');
    if (orderTime) formData.append('order_time', orderTime);
    if (remark) formData.append('remark', remark);
    
    const result = await fetchAPI('/api/orders/batch/quantity', {
        method: 'POST',
        body: formData
    });
    
    alert(result.success ? `刷单完成，共 ${result.order_count} 个订单` : '刷单失败: ' + (result.message || '未知错误'));
});

// === 初始化 ===

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('store-count')) {
        loadStatus();
        loadStoreCount();
        loadDishCount();
    }
});