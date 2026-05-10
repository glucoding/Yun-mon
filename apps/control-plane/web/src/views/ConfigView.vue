<template>
  <div class="config-view">
    <p class="muted">完整 desired-state JSON 编辑器。点击 <strong>保存并下发</strong> 会触发 Pydantic 校验、渲染、Prometheus 热重载、并写一份审计快照。</p>
    <textarea v-model="text" class="json-editor" spellcheck="false"></textarea>
    <div class="actions">
      <button class="btn btn-primary" @click="save" :disabled="saving">
        {{ saving ? '保存中…' : '保存并下发' }}
      </button>
      <button class="btn btn-ghost" @click="reset">还原为已下发版本</button>
      <span v-if="message" class="message" :class="messageKind">{{ message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from 'vue';
import { useConfigStore } from '../stores/config';

const store = useConfigStore();
const text = ref('{}');
const saving = ref(false);
const message = ref('');
const messageKind = ref<'ok' | 'err'>('ok');

watchEffect(() => {
  if (store.draft) text.value = JSON.stringify(store.draft, null, 2);
});

async function save() {
  message.value = '';
  saving.value = true;
  try {
    let parsed: Record<string, any>;
    try {
      parsed = JSON.parse(text.value);
    } catch (err) {
      message.value = `JSON 语法错误: ${(err as Error).message}`;
      messageKind.value = 'err';
      return;
    }
    store.draft = parsed;
    const ok = await store.applyDraft();
    if (ok) {
      message.value = '已下发,Prometheus 已热重载';
      messageKind.value = 'ok';
    } else {
      message.value = `下发失败: ${store.lastError ?? '未知错误'}`;
      messageKind.value = 'err';
    }
  } finally {
    saving.value = false;
  }
}

function reset() {
  if (store.config) text.value = JSON.stringify(store.config, null, 2);
}
</script>
