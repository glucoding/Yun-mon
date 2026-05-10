<template>
  <div class="grid">
    <article class="card">
      <h3>系统信息</h3>
      <dl class="kv">
        <dt>项目</dt>
        <dd>{{ system.monitoringProject }}</dd>
        <dt>环境</dt>
        <dd>{{ system.environment }}</dd>
        <dt>集群名</dt>
        <dd>{{ system.clusterName }}</dd>
        <dt>schema 版本</dt>
        <dd>{{ store.config?.metadata?.schemaVersion ?? '-' }}</dd>
      </dl>
    </article>

    <article class="card">
      <h3>运行态</h3>
      <p v-if="runtime" class="muted">
        重启策略：<strong>{{ (runtime as any).runtime?.restartStrategy ?? '-' }}</strong>
      </p>
      <p v-if="runtime" class="muted">
        Stack-agent 可达：
        <strong>{{ (runtime as any).runtime?.stackAgent?.reachable ? '是' : '否' }}</strong>
      </p>
      <button class="btn" @click="restart" :disabled="restartLoading">
        {{ restartLoading ? '正在重建…' : '保存并重建监测栈' }}
      </button>
      <p v-if="lastJobId" class="muted">最近任务: {{ lastJobId }}</p>
    </article>

    <article class="card">
      <h3>容器列表</h3>
      <ul class="container-list">
        <li v-for="svc in services" :key="(svc as any).name">
          <strong>{{ (svc as any).service || (svc as any).name }}</strong>
          <span class="badge" :class="`badge-${(svc as any).state}`">{{ (svc as any).state }}</span>
          <small>{{ ((svc as any).ports as string[]).join(', ') || '—' }}</small>
        </li>
      </ul>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useConfigStore } from '../stores/config';
import { api } from '../api/client';

const store = useConfigStore();
const services = ref<Array<Record<string, unknown>>>([]);
const runtime = ref<Record<string, unknown> | null>(null);
const restartLoading = ref(false);
const lastJobId = ref<string | null>(null);

const system = computed(() => store.config?.system ?? { monitoringProject: '-', environment: '-', clusterName: '-' });

async function loadAll() {
  try {
    const list = (await api.listServices()) as { ok: boolean; services: Array<Record<string, unknown>> };
    services.value = list.services ?? [];
  } catch {
    services.value = [];
  }
  try {
    runtime.value = await api.runtime();
  } catch {
    runtime.value = null;
  }
}

async function restart() {
  restartLoading.value = true;
  try {
    if (store.draft) {
      await store.applyDraft();
    }
    const job = await api.restart({ build: true, includeControlPlane: false });
    lastJobId.value = job.jobId;
  } finally {
    restartLoading.value = false;
    loadAll();
  }
}

onMounted(loadAll);
</script>
