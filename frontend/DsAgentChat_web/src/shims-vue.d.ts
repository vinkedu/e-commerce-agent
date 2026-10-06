/// <reference types="tdesign-vue-next/global" />
/// <reference types="@tdesign-vue-next/chat/global" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
} 