<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { DialogPlugin } from 'tdesign-vue-next'
import { AuthService } from '../services/api'
import { useConversationStore } from '../stores/conversation'

const router = useRouter()
const conversationStore = useConversationStore()
const activeTab = ref<'login' | 'register'>('login')

const form = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreement: false,
})

const errors = ref({
  username: '',
  email: '',
  password: '',
  general: '',
})

const validateRules = {
  username: {
    pattern: /^[a-zA-Z0-9_]{4,16}$/,
    message: '用户名必须是4-16位字母、数字或下划线',
  },
  email: {
    pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
    message: '请输入有效的邮箱地址',
  },
  password: {
    pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d]{8,}$/,
    message: '密码必须包含大小写字母和数字，至少8位',
  },
}

const validate = (field: 'username' | 'email' | 'password', value: string) => {
  if (!value) {
    errors.value[field] = `请输入${field === 'username' ? '用户名' : field === 'email' ? '邮箱' : '密码'}`
    return false
  }
  if (!validateRules[field].pattern.test(value)) {
    errors.value[field] = validateRules[field].message
    return false
  }
  errors.value[field] = ''
  return true
}

const isFormValid = computed(() => {
  if (activeTab.value === 'login') {
    return (
      !!form.value.email &&
      !!form.value.password &&
      form.value.agreement &&
      validate('email', form.value.email) &&
      validate('password', form.value.password)
    )
  }
  return (
    !!form.value.username &&
    !!form.value.email &&
    !!form.value.password &&
    !!form.value.confirmPassword &&
    form.value.password === form.value.confirmPassword &&
    form.value.agreement &&
    validate('username', form.value.username) &&
    validate('email', form.value.email) &&
    validate('password', form.value.password)
  )
})

const clearErrors = () => {
  errors.value = { username: '', email: '', password: '', general: '' }
}

const handleSubmit = async () => {
  if (!form.value.agreement) {
    errors.value.general = '请先同意用户协议和隐私政策'
    return
  }
  if (!isFormValid.value) return
  clearErrors()

  try {
    if (activeTab.value === 'register') {
      await AuthService.register({
        username: form.value.username,
        email: form.value.email,
        password: form.value.password,
      })
      showRegisterSuccess()
    } else {
      const response = await AuthService.login({
        email: form.value.email,
        password: form.value.password,
      })
      localStorage.setItem('token', response.access_token)
      const userInfo = await AuthService.getUserInfo()
      localStorage.setItem('user_id', userInfo.id.toString())
      await conversationStore.createNewConversation()
      router.push('/')
    }
  } catch (error: any) {
    if (error.response?.status === 401) {
      errors.value.general = '邮箱或密码错误'
    } else if (error.response?.data?.detail) {
      const detail = error.response.data.detail
      if (typeof detail === 'string') {
        errors.value.general = detail
      } else if (Array.isArray(detail)) {
        detail.forEach((err: any) => {
          const field = err.loc[1]
          errors.value[field as keyof typeof errors.value] = err.msg
        })
      }
    } else {
      errors.value.general = '发生错误，请稍后重试'
    }
  }
}

function showRegisterSuccess() {
  const dialog = DialogPlugin.confirm({
    header: '注册成功',
    body: '请使用注册的账号登录',
    confirmBtn: '去登录',
    cancelBtn: null,
    onConfirm: () => {
      switchTo('login')
      form.value = {
        username: form.value.username,
        email: form.value.email,
        password: '',
        confirmPassword: '',
        agreement: false,
      }
      dialog.destroy()
    },
  })
}

function switchTo(tab: 'login' | 'register') {
  activeTab.value = tab
  clearErrors()
  router.replace(`/${tab}`)
}

const showTerms = () => {
  /* TODO: 显示用户协议 */
}
const showPrivacy = () => {
  /* TODO: 显示隐私政策 */
}
const handleWechatLogin = () => {
  /* TODO: 微信登录逻辑 */
}

onMounted(() => {
  activeTab.value = router.currentRoute.value.path === '/register' ? 'register' : 'login'
})

watch(
  () => form.value.username,
  (val) => {
    if (activeTab.value === 'register' && val) validate('username', val)
  },
)
watch(
  () => form.value.email,
  (val) => {
    if (val) validate('email', val)
  },
)
watch(
  () => form.value.password,
  (val) => {
    if (val) validate('password', val)
  },
)
</script>

<template>
  <div class="login-container">
    <div class="login-box">
      <div class="logo">
        <span class="brand">AssistGen</span>
      </div>
      <h2 class="login-title">{{ activeTab === 'login' ? '账号登录' : '注册账号' }}</h2>

      <div class="form-container">
        <t-alert v-if="errors.general" theme="error" :message="errors.general" class="general-error" />

        <div v-if="activeTab === 'register'" class="input-group">
          <t-input
            v-model="form.username"
            placeholder="请输入用户名"
            :status="errors.username ? 'error' : undefined"
            :tips="errors.username || undefined"
            size="large"
          />
        </div>

        <div class="input-group">
          <t-input
            v-model="form.email"
            placeholder="请输入邮箱"
            :status="errors.email ? 'error' : undefined"
            :tips="errors.email || undefined"
            size="large"
          />
        </div>

        <div class="input-group">
          <t-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :status="errors.password ? 'error' : undefined"
            :tips="errors.password || undefined"
            size="large"
          />
        </div>

        <div v-if="activeTab === 'register'" class="input-group">
          <t-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请确认密码"
            size="large"
          />
        </div>

        <t-checkbox v-model="form.agreement" class="agreement">
          我已同意
          <a href="#" @click.prevent="showTerms">用户协议</a>
          与
          <a href="#" @click.prevent="showPrivacy">隐私政策</a>
        </t-checkbox>

        <t-button
          theme="primary"
          size="large"
          block
          :disabled="!isFormValid"
          class="submit-btn"
          @click="handleSubmit"
        >
          {{ activeTab === 'login' ? '登录' : '注册' }}
        </t-button>

        <div class="register-link">
          {{ activeTab === 'login' ? '还没有账号？' : '已有账号？' }}
          <a href="#" @click.prevent="switchTo(activeTab === 'login' ? 'register' : 'login')">
            {{ activeTab === 'login' ? '立即注册' : '返回登录' }}
          </a>
        </div>

        <div v-if="activeTab === 'login'" class="other-login">
          <div class="divider"><span>其他登录方式</span></div>
          <t-button variant="outline" size="large" block @click="handleWechatLogin">
            使用微信登录
          </t-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--td-bg-color-page);
}
.login-box {
  width: 400px;
  padding: 40px;
  background: var(--td-bg-color-container);
  border-radius: 12px;
  box-shadow: var(--td-shadow-2);
}
.logo {
  text-align: center;
  margin-bottom: 24px;
}
.brand {
  font-size: 24px;
  font-weight: 700;
  color: var(--td-brand-color);
}
.login-title {
  color: var(--td-text-color-primary);
  font-size: 22px;
  font-weight: 500;
  text-align: center;
  margin-bottom: 28px;
}
.general-error {
  margin-bottom: 16px;
}
.input-group {
  margin-bottom: 18px;
}
.agreement {
  margin-bottom: 20px;
  color: var(--td-text-color-secondary);
}
.agreement a {
  color: var(--td-brand-color);
  text-decoration: none;
}
.agreement a:hover {
  text-decoration: underline;
}
.register-link {
  text-align: center;
  margin-top: 16px;
  color: var(--td-text-color-secondary);
  font-size: 14px;
}
.register-link a {
  color: var(--td-brand-color);
  text-decoration: none;
  margin-left: 8px;
}
.register-link a:hover {
  text-decoration: underline;
}
.other-login {
  margin-top: 28px;
}
.divider {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  color: var(--td-text-color-placeholder);
  font-size: 13px;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--td-component-stroke);
  margin: 0 16px;
}
</style>
