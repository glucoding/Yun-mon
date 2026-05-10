<template>
  <div>
    <p class="muted">
      列出当前 Compose 项目下被 control-plane 自动发现 / 手工纳管的应用。<code>monitoring_enabled=true</code>
      label 会自动启用采集。
    </p>
    <table class="data-table">
      <thead>
        <tr>
          <th>App ID</th>
          <th>展示名</th>
          <th>是否启用</th>
          <th>采集端口</th>
          <th>Targets</th>
          <th>来源</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="app in items" :key="app.appId">
          <td><code>{{ app.appId }}</code></td>
          <td>{{ app.displayName }}</td>
          <td>{{ app.enabled ? '是' : '否' }}</td>
          <td>{{ app.targetPort ?? '-' }}</td>
          <td>{{ (app.targets ?? []).join(', ') || '-' }}</td>
          <td>{{ app.discoveryType }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="lastError" class="error">{{ lastError }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '../api/client';

interface AppItem {
  appId: string;
  displayName?: string;
  enabled?: boolean;
  targetPort?: number | null;
  targets?: string[];
  discoveryType?: string;
}

const items = ref<AppItem[]>([]);
const lastError = ref('');

async function load() {
  try {
    const payload = (await api.applications()) as { ok: boolean; applications: AppItem[] };
    items.value = payload.applications;
  } catch (err) {
    lastError.value = (err as Error).message;
  }
}

onMounted(load);
</script>
