<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConversationStore } from '../stores/conversation'
import { useUserStore } from '../stores/user'
import { AuthService } from '../services/api'

const emit = defineEmits<{ select: [id: number] }>()
const convStore = useConversationStore()
const userStore = useUserStore()

const renameVisible = ref(false)
const renameId = ref<number | null>(null)
const renameText = ref('')

onMounted(() => {
  convStore.loadUserConversations().catch(() => {})
})

async function onNew() {
  const id = await convStore.createNewConversation()
  if (id) emit('select', id)
}
function openRename(id: number, cur: string) {
  renameId.value = id
  renameText.value = cur || ''
  renameVisible.value = true
}
async function confirmRename() {
  if (renameId.value && renameText.value.trim()) {
    await convStore.updateConversationName(renameId.value, renameText.value.trim())
  }
  renameVisible.value = false
}
async function onDelete(id: number) {
  await convStore.deleteConversation(id)
}
function onLogout() {
  AuthService.logout()
}
</script>

<template>
  <div class="conv-sidebar">
    <div class="conv-head">
      <span class="logo">AssistGen</span>
    </div>
    <t-button theme="primary" block class="new-btn" @click="onNew">+ 新会话</t-button>
    <div class="conv-section-title">任务历史</div>
    <ul class="conv-list">
      <li
        v-for="c in convStore.conversations"
        :key="c.id"
        :class="{ active: c.id === convStore.currentConversationId }"
        @click="emit('select', c.id)"
      >
        <span class="conv-title">{{ c.title || '新会话' }}</span>
        <span class="conv-actions" @click.stop>
          <t-button variant="text" size="small" @click="openRename(c.id, c.title)">改名</t-button>
          <t-popconfirm content="确定删除该会话？" @confirm="onDelete(c.id)">
            <t-button variant="text" size="small" theme="danger">删除</t-button>
          </t-popconfirm>
        </span>
      </li>
    </ul>
    <div class="conv-foot">
      <t-avatar size="small">{{ (userStore.username || 'U').charAt(0) }}</t-avatar>
      <span class="uname">{{ userStore.username || '用户' }}</span>
      <t-button variant="text" size="small" @click="onLogout">退出</t-button>
    </div>
    <t-dialog v-model:visible="renameVisible" header="重命名会话" @confirm="confirmRename">
      <t-input v-model="renameText" placeholder="输入会话名称" />
    </t-dialog>
  </div>
</template>

<style scoped>
.conv-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
  box-sizing: border-box;
}
.conv-head {
  display: flex;
  align-items: center;
  padding: 8px 4px 16px;
}
.logo {
  font-size: 18px;
  font-weight: 600;
  color: var(--td-brand-color);
}
.new-btn {
  margin-bottom: 16px;
}
.conv-section-title {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  padding: 4px;
}
.conv-list {
  list-style: none;
  margin: 0;
  padding: 0;
  flex: 1;
  overflow-y: auto;
}
.conv-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}
.conv-list li:hover {
  background: var(--td-bg-color-container-hover);
}
.conv-list li.active {
  background: var(--td-brand-color-light);
}
.conv-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.conv-actions {
  display: none;
}
.conv-list li:hover .conv-actions {
  display: inline-flex;
}
.conv-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--td-component-stroke);
}
.uname {
  flex: 1;
  font-size: 14px;
}
</style>
