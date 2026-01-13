/**
 * 谷歌账号管理系统 - 通用JS工具
 */

// ==================== Toast 消息提示 ====================

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'check-circle';
    if (type === 'error') icon = 'x-circle';
    if (type === 'warning') icon = 'alert-circle';
    
    toast.innerHTML = `
        <i data-lucide="${icon}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    lucide.createIcons();
    
    // 3秒后自动移除
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==================== 模态框 ====================

function showModal(title, content, onConfirm) {
    const container = document.getElementById('modal-container');
    
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>${title}</h3>
                <button class="modal-close" onclick="closeModal()">
                    <i data-lucide="x"></i>
                </button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
            <div class="modal-footer">
                <button class="btn btn-outline" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" id="modal-confirm">确定</button>
            </div>
        </div>
    `;
    
    container.appendChild(modal);
    lucide.createIcons();
    
    // 绑定确认按钮
    document.getElementById('modal-confirm').onclick = onConfirm;
}

function closeModal() {
    const container = document.getElementById('modal-container');
    container.innerHTML = '';
}

// ==================== 表格选择功能 ====================

function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(cb => cb.checked = checkbox.checked);
    updateSelection();
}

function updateSelection() {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    const checkedBoxes = document.querySelectorAll('.row-checkbox:checked');
    const selectAll = document.getElementById('select-all');
    const batchBar = document.getElementById('batch-bar');
    const countEl = document.getElementById('selected-count');
    
    // 更新全选框状态
    if (checkboxes.length > 0) {
        selectAll.checked = checkedBoxes.length === checkboxes.length;
        selectAll.indeterminate = checkedBoxes.length > 0 && checkedBoxes.length < checkboxes.length;
    }
    
    // 显示/隐藏批量操作栏
    if (checkedBoxes.length > 0) {
        batchBar.classList.add('show');
        countEl.textContent = checkedBoxes.length;
    } else {
        batchBar.classList.remove('show');
    }
}

function getSelectedIds() {
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    return Array.from(checkboxes).map(cb => parseInt(cb.value));
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(cb => cb.checked = false);
    const selectAll = document.getElementById('select-all');
    if (selectAll) selectAll.checked = false;
    updateSelection();
}

// ==================== 工具函数 ====================

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 侧边栏菜单 ====================

document.addEventListener('DOMContentLoaded', () => {
    // 菜单折叠/展开
    const navGroupTitles = document.querySelectorAll('.nav-group-title');
    navGroupTitles.forEach(title => {
        title.addEventListener('click', () => {
            const group = title.parentElement;
            group.classList.toggle('collapsed');
        });
    });
});

